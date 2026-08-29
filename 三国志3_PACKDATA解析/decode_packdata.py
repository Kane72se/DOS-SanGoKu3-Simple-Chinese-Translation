#!/usr/bin/env python3
"""
PACKDATA.DAT -- 三国志III (DOS, KOEI 1992) PACKDATA 解析

文件: 169,054 字节, 日期 1992/7/8 (与 OPENGRP.DAT 同期)
结论:
  1. 1993 版开场程序 OPEN.EXE 只在启动时检查该文件是否存在, 从不读取其内容
     (OPEN.EXE 数据段 0x17E6 处的文件名偏移 0x1242 -> "PACKDATA.DAT",
      调用 0xD9 打开+关闭做存在性检查)。因此它是 1992 原版开场遗留文件。
  2. 文件内容为 KOEI NPK 式压缩图形流(与 OPEN.EXE 内部解压例程 0x1C81 同款,
     具有 0x38 特殊 token、3 字节为一组的位平面结构)。
  3. 用游戏自身解压例程(本脚本内嵌 8086 模拟)解码文件头 (256,168) 后的数据,
     得到 168 行 x 96 字节的缓冲区: 按 3 位平面/8 像素解读为 256x168 图形,
     主体为条纹底纹, 边缘有装饰图案。
"""

import os
import struct
import sys

from PIL import Image

OPEN_EXE = r"C:/Users/admin/Downloads/dos/san3/OPEN.EXE"
PACK = r"C:/Users/admin/Downloads/dos/san3/PACKDATA.DAT"

PAL8 = [
    (0x00, 0x00, 0x00),
    (0x10, 0xB2, 0x51),
    (0xF3, 0x51, 0x00),
    (0xF3, 0xE3, 0x00),
    (0x00, 0x41, 0xF3),
    (0x00, 0xC3, 0xF3),
    (0xF3, 0x51, 0xD3),
    (0xF3, 0xF3, 0xF3),
]


# ---------------------------------------------------------------- 8086 mini emulator
class CPU:
    def __init__(self, code: bytes):
        self.code = code
        self.regs = {"ax": 0, "bx": 0, "cx": 0, "dx": 0, "si": 0, "di": 0, "bp": 0, "sp": 0}
        self.seg = {"cs": 0x1000, "ds": 0, "es": 0, "ss": 0}
        self.mem = {}
        self.ip = 0
        self.cf = self.zf = self.sf = 0
        self.steps = 0
        self.max_di = 0
        self.max_out_addr = -1

    def rd(self, seg, off):
        return self.mem.get((seg, off & 0xFFFF), 0) & 0xFFFF

    def wr(self, seg, off, v):
        self.mem[(seg, off & 0xFFFF)] = v & 0xFFFF

    def rdb(self, seg, off):
        return self.mem.get((seg, off & 0xFFFF), 0) & 0xFF

    def wrb(self, seg, off, v):
        off &= 0xFFFF
        if seg == 0x3000 and off > self.max_out_addr:
            self.max_out_addr = off
        self.mem[(seg, off)] = v & 0xFF

    def push16(self, v):
        self.regs["sp"] = (self.regs["sp"] - 2) & 0xFFFF
        self.wr(self.seg["ss"], self.regs["sp"], v)

    def pop16(self):
        v = self.rd(self.seg["ss"], self.regs["sp"])
        self.regs["sp"] = (self.regs["sp"] + 2) & 0xFFFF
        return v

    def r8(self, name):
        m = {"al": ("ax", 0), "ah": ("ax", 8), "bl": ("bx", 0), "bh": ("bx", 8),
             "cl": ("cx", 0), "ch": ("cx", 8), "dl": ("dx", 0), "dh": ("dx", 8)}
        r, s = m[name]
        return (self.regs[r] >> s) & 0xFF

    def s8(self, name, v):
        m = {"al": ("ax", 0), "ah": ("ax", 8), "bl": ("bx", 0), "bh": ("bx", 8),
             "cl": ("cx", 0), "ch": ("cx", 8), "dl": ("dx", 0), "dh": ("dx", 8)}
        r, s = m[name]
        mask = 0xFF << s
        self.regs[r] = (self.regs[r] & ~mask) | ((v & 0xFF) << s)

    def flags_set(self, v):
        self.zf = 1 if v == 0 else 0
        self.sf = 1 if v & 0x8000 else 0

    def load(self, seg, off, data):
        for i, x in enumerate(data):
            self.wrb(seg, off + i, x)

    def run(self, start, max_steps):
        self.ip = start
        while self.steps < max_steps:
            if self.ip >= len(self.code):
                break
            if self.regs["di"] > self.max_di:
                self.max_di = self.regs["di"]
            self.steps += 1
            op = self.code[self.ip]
            if not self.step(op):
                break
        return self.steps

    def jcc(self, op):
        rel = self.code[self.ip + 1]
        if rel >= 0x80:
            rel -= 0x100
        t = {
            0x74: self.zf == 1,
            0x75: self.zf == 0,
            0x72: self.cf == 1,
            0x73: self.cf == 0,
            0x76: self.cf == 1 or self.zf == 1,
            0x77: not (self.cf == 1 or self.zf == 1),
            0x7C: self.sf != 0,
            0x7D: self.sf == 0,
            0x7E: self.sf != 0 or self.zf == 1,
            0x7F: self.sf == 0 and self.zf == 0,
        }.get(op, False)
        self.ip = (self.ip + 2 + rel) & 0xFFFF if t else (self.ip + 2) & 0xFFFF
        return True

    def arith(self, op, a, b):
        if op in (0x01, 0x03):
            r = a + b
            self.flags_set(r)
            self.cf = 1 if r > 0xFFFF else 0
            return r & 0xFFFF
        if op in (0x29, 0x2B, 0x39, 0x3B):
            r = a - b
            self.flags_set(r)
            self.cf = 1 if a < b else 0
            return (a & 0xFFFF) if op in (0x39, 0x3B) else (r & 0xFFFF)
        if op in (0x21, 0x23):
            r = a & b
            self.flags_set(r)
            self.cf = 0
            return r
        if op in (0x09, 0x0B):
            r = a | b
            self.flags_set(r)
            self.cf = 0
            return r
        if op in (0x31, 0x33):
            r = a ^ b
            self.flags_set(r)
            self.cf = 0
            return r
        if op in (0x80, 0x81, 0x83):
            r = a + b
            self.flags_set(r)
            self.cf = 1 if r > 0xFFFF else 0
            return r & 0xFFFF
        raise ValueError(hex(op))

    def arith8(self, op, a, b):
        if op in (0x80, 0x00, 0x02):
            r = a + b
            self.zf = 1 if (r & 0xFF) == 0 else 0
            self.sf = 1 if r & 0x80 else 0
            self.cf = 1 if r > 0xFF else 0
            return r & 0xFF
        if op in (0x28, 0x2A, 0x38, 0x3A):
            r = a - b
            self.zf = 1 if (r & 0xFF) == 0 else 0
            self.sf = 1 if r & 0x80 else 0
            self.cf = 1 if a < b else 0
            return (r & 0xFF) if op not in (0x38, 0x3A) else (a & 0xFF)
        if op in (0x20, 0x22):
            r = a & b
            self.zf = 1 if (r & 0xFF) == 0 else 0
            self.sf = 1 if r & 0x80 else 0
            self.cf = 0
            return r & 0xFF
        if op in (0x08, 0x0A):
            r = a | b
            self.zf = 1 if (r & 0xFF) == 0 else 0
            self.sf = 1 if r & 0x80 else 0
            self.cf = 0
            return r & 0xFF
        if op in (0x30, 0x32):
            r = a ^ b
            self.zf = 1 if (r & 0xFF) == 0 else 0
            self.sf = 1 if r & 0x80 else 0
            self.cf = 0
            return r & 0xFF
        raise ValueError(hex(op))

    def shift_once(self, reg, v, bits=16):
        mask = 0xFF if bits == 8 else 0xFFFF
        top = 0x80 if bits == 8 else 0x8000
        v &= mask
        if reg in (4, 6):
            self.cf = 1 if v & top else 0
            r = (v << 1) & mask
            self.flags_set(r)
            return r
        if reg == 5:
            self.cf = v & 1
            r = v >> 1
            self.flags_set(r)
            return r
        if reg == 2:
            newcf = 1 if v & top else 0
            r = ((v << 1) | self.cf) & mask
            self.cf = newcf
            return r
        if reg == 3:
            newcf = v & 1
            r = (v >> 1) | (self.cf << (bits - 1))
            self.cf = newcf
            return r
        if reg == 7:
            self.cf = v & 1
            r = (v >> 1) | (v & top)
            self.flags_set(r)
            return r
        raise ValueError(reg)

    def modrm(self, op):
        c = self.code
        ip = self.ip
        modrm = c[ip + 1]
        self.ip += 2
        mod, reg, rm = (modrm >> 6) & 3, (modrm >> 3) & 7, modrm & 7
        disp = 0
        if mod == 0 and rm == 6:
            disp = c[self.ip] | (c[self.ip + 1] << 8)
            self.ip += 2
        elif mod == 1:
            disp = c[self.ip]
            if disp >= 0x80:
                disp -= 0x100
            self.ip += 1
        elif mod == 2:
            disp = c[self.ip] | (c[self.ip + 1] << 8)
            if disp >= 0x8000:
                disp -= 0x10000
            self.ip += 2
        rn = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][reg]
        r8n = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
        rm8n = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
        rm_seg = self.seg["ds"]
        if mod == 3:
            rm_val = self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][rm]]
        else:
            base, idx = None, None
            if rm == 0:
                base, idx = "bx", "si"
            elif rm == 1:
                base, idx = "bx", "di"
            elif rm == 2:
                base, idx = "bp", "si"
            elif rm == 3:
                base, idx = "bp", "di"
            elif rm == 4:
                base, idx = "si", None
            elif rm == 5:
                base, idx = "di", None
            elif rm == 6:
                base, idx = "bp", None
            else:
                base, idx = "bx", None
            ea = ((self.regs[base] if base else 0) + (self.regs[idx] if idx else 0) + disp) & 0xFFFF
            rm_seg = self.seg["ss"] if base == "bp" else self.seg["ds"]
            rm_val = ea
        if op == 0x8B:
            self.regs[rn] = self.rd(rm_seg, rm_val) if mod != 3 else rm_val
            return True
        if op == 0x8A:
            self.s8(r8n[reg], self.rdb(rm_seg, rm_val) if mod != 3 else self.r8(rm8n[rm]))
            return True
        if op == 0x89:
            if mod == 3:
                self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][rm]] = self.regs[rn]
            else:
                self.wr(rm_seg, rm_val, self.regs[rn])
            return True
        if op == 0x88:
            if mod == 3:
                self.s8(rm8n[rm], self.r8(r8n[reg]))
            else:
                self.wrb(rm_seg, rm_val, self.r8(r8n[reg]))
            return True
        if op == 0x8E:
            v = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
            sreg = ["es", "cs", "ss", "ds"][reg] if reg < 4 else None
            if sreg:
                self.seg[sreg] = v
            return True
        if op == 0xC4:
            self.regs[rn] = self.rd(rm_seg, rm_val)
            self.seg["es"] = self.rd(rm_seg, (rm_val + 2) & 0xFFFF)
            return True
        if op == 0x8D:
            self.regs[rn] = rm_val & 0xFFFF
            return True
        if op in (0x02, 0x2A, 0x22, 0x0A, 0x32, 0x3A):
            cur = self.r8(rm8n[rm]) if mod == 3 else self.rdb(rm_seg, rm_val)
            self.s8(r8n[reg], self.arith8(op, cur, self.r8(r8n[reg])))
            return True
        if op in (0x00, 0x28, 0x20, 0x08, 0x30, 0x38):
            v = self.r8(r8n[reg])
            cur = self.r8(rm8n[rm]) if mod == 3 else self.rdb(rm_seg, rm_val)
            r = self.arith8(op, cur, v)
            if mod == 3:
                self.s8(rm8n[rm], r)
            else:
                self.wrb(rm_seg, rm_val, r)
            return True
        if op in (0x01, 0x29, 0x21, 0x09, 0x0B, 0x31, 0x39):
            v = self.regs[rn]
            cur = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
            r = self.arith(op, cur, v)
            if mod == 3:
                self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][rm]] = r
            else:
                self.wr(rm_seg, rm_val, r)
            return True
        if op in (0x03, 0x2B, 0x23, 0x0B, 0x33, 0x3B):
            self.regs[rn] = self.arith(op, rm_val if mod == 3 else self.rd(rm_seg, rm_val), self.regs[rn])
            return True
        if op == 0x85:
            r = (rm_val if mod == 3 else self.rd(rm_seg, rm_val)) & self.regs[rn]
            self.zf = 1 if r == 0 else 0
            self.sf = 1 if r & 0x8000 else 0
            return True
        if op in (0x81, 0x83):
            if op == 0x81:
                imm = c[self.ip] | (c[self.ip + 1] << 8)
                if imm >= 0x8000:
                    imm -= 0x10000
                self.ip += 2
            else:
                imm = c[self.ip]
                if imm >= 0x80:
                    imm -= 0x100
                self.ip += 1
            cur = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
            r = self.arith({0x81: {0: 0x01, 5: 0x29, 4: 0x21, 1: 0x09, 6: 0x31, 7: 0x39}.get(reg, 0x01),
                             0x83: {0: 0x01, 5: 0x29, 4: 0x21, 1: 0x09, 6: 0x31, 7: 0x39}.get(reg, 0x01)}[op], cur, imm)
            if mod == 3:
                self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][rm]] = r
            else:
                self.wr(rm_seg, rm_val, r)
            return True
        if op == 0x80:
            imm = c[self.ip]
            self.ip += 1
            cur = self.r8(rm8n[rm]) if mod == 3 else self.rdb(rm_seg, rm_val)
            r = self.arith8({0: 0x00, 5: 0x28, 4: 0x20, 1: 0x08, 6: 0x30, 7: 0x38}.get(reg, 0x00), cur, imm)
            if mod == 3:
                self.s8(rm8n[rm], r)
            else:
                self.wrb(rm_seg, rm_val, r)
            return True
        if op in (0xD0, 0xD1, 0xD2, 0xD3):
            cnt = (self.regs["cx"] & 0xFF) if op in (0xD2, 0xD3) else 1
            is8 = op in (0xD0, 0xD2)
            if mod == 3:
                if is8:
                    n8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"][rm]
                    v = self.r8(n8)
                    for _ in range(cnt):
                        v = self.shift_once(reg, v, 8)
                    self.s8(n8, v)
                else:
                    n = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][rm]
                    v = self.regs[n]
                    for _ in range(cnt):
                        v = self.shift_once(reg, v, 16)
                    self.regs[n] = v
            else:
                v = self.rd(rm_seg, rm_val)
                for _ in range(cnt):
                    v = self.shift_once(reg, v, 8 if is8 else 16)
                self.wr(rm_seg, rm_val, v)
            return True
        if op == 0xF7:
            if reg == 0:
                imm = c[self.ip] | (c[self.ip + 1] << 8)
                self.ip += 2
                r = (rm_val if mod == 3 else self.rd(rm_seg, rm_val)) & imm
                self.zf = 1 if r == 0 else 0
                self.sf = 1 if r & 0x8000 else 0
                return True
            if reg == 5:
                cur = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
                if cur & 0x8000:
                    cur -= 0x10000
                ax = self.regs["ax"]
                if ax & 0x8000:
                    ax -= 0x10000
                r = ax * cur
                self.regs["ax"] = r & 0xFFFF
                self.regs["dx"] = (r >> 16) & 0xFFFF
                return True
            if reg == 6:
                cur = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
                r = self.regs["ax"] * cur
                self.regs["ax"] = r & 0xFFFF
                self.regs["dx"] = (r >> 16) & 0xFFFF
                return True
            return False
        if op == 0xF6:
            if reg == 0:
                imm = c[self.ip]
                self.ip += 1
                cur = self.rdb(rm_seg, rm_val) if mod != 3 else self.r8(rm8n[rm])
                r = cur & imm
                self.zf = 1 if r == 0 else 0
                self.sf = 1 if r & 0x80 else 0
                return True
            return False
        if op == 0xFF:
            v = rm_val if mod == 3 else self.rd(rm_seg, rm_val)
            if reg == 4:
                self.ip = v
                return True
            if reg == 6:
                self.push16(v)
                return True
            if reg == 2:
                self.push16(self.ip)
                self.ip = v
                return True
            return False
        if op == 0xFE:
            cur = self.rdb(rm_seg, rm_val) if mod != 3 else self.r8(rm8n[rm])
            nv = (cur + 1) & 0xFF if reg == 0 else (cur - 1) & 0xFF
            if mod == 3:
                self.s8(rm8n[rm], nv)
            else:
                self.wrb(rm_seg, rm_val, nv)
            self.zf = 1 if nv == 0 else 0
            self.sf = 1 if nv & 0x80 else 0
            return True
        return False

    def step(self, op):
        c = self.code
        ip = self.ip
        if 0x50 <= op <= 0x57:
            self.push16(self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][op - 0x50]])
            self.ip += 1
            return True
        if 0x58 <= op <= 0x5F:
            self.regs[["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][op - 0x58]] = self.pop16()
            self.ip += 1
            return True
        if op in (0x1E, 0x06, 0x16, 0x0E):
            self.push16(self.seg[{0x1E: "ds", 0x06: "es", 0x16: "ss", 0x0E: "cs"}[op]])
            self.ip += 1
            return True
        if op in (0x1F, 0x07, 0x17):
            self.seg[{0x1F: "ds", 0x07: "es", 0x17: "ss"}[op]] = self.pop16()
            self.ip += 1
            return True
        if 0x40 <= op <= 0x47:
            r = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][op - 0x40]
            self.regs[r] = (self.regs[r] + 1) & 0xFFFF
            self.flags_set(self.regs[r])
            self.ip += 1
            return True
        if 0x48 <= op <= 0x4F:
            r = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][op - 0x48]
            self.regs[r] = (self.regs[r] - 1) & 0xFFFF
            self.flags_set(self.regs[r])
            self.ip += 1
            return True
        if op == 0x90:
            self.ip += 1
            return True
        if op == 0x91:
            self.regs["ax"], self.regs["cx"] = self.regs["cx"], self.regs["ax"]
            self.ip += 1
            return True
        if op == 0xFC:
            self.ip += 1
            return True
        if op == 0xF8:
            self.cf = 0
            self.ip += 1
            return True
        if op == 0x99:
            self.regs["dx"] = 0xFFFF if self.regs["ax"] & 0x8000 else 0
            self.ip += 1
            return True
        if 0xB8 <= op <= 0xBF:
            r = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"][op - 0xB8]
            self.regs[r] = c[ip + 1] | (c[ip + 2] << 8)
            self.ip += 3
            return True
        if op == 0xAC:
            self.s8("al", self.rdb(self.seg["ds"], self.regs["si"]))
            self.regs["si"] = (self.regs["si"] + 1) & 0xFFFF
            self.ip += 1
            return True
        if op == 0xAA:
            self.wrb(self.seg["es"], self.regs["di"], self.r8("al"))
            self.regs["di"] = (self.regs["di"] + 1) & 0xFFFF
            self.ip += 1
            return True
        if op == 0xA4:
            self.wrb(self.seg["es"], self.regs["di"], self.rdb(self.seg["ds"], self.regs["si"]))
            self.regs["si"] = (self.regs["si"] + 1) & 0xFFFF
            self.regs["di"] = (self.regs["di"] + 1) & 0xFFFF
            self.ip += 1
            return True
        if op == 0xE2:
            rel = c[ip + 1]
            if rel >= 0x80:
                rel -= 0x100
            self.regs["cx"] -= 1
            self.ip += 2
            if self.regs["cx"] != 0:
                self.ip = (self.ip + rel) & 0xFFFF
            return True
        if op == 0xEB:
            rel = c[ip + 1]
            if rel >= 0x80:
                rel -= 0x100
            self.ip = (self.ip + 2 + rel) & 0xFFFF
            return True
        if op == 0xE9:
            rel = c[ip + 1] | (c[ip + 2] << 8)
            if rel >= 0x8000:
                rel -= 0x10000
            self.ip = (self.ip + 3 + rel) & 0xFFFF
            return True
        if op == 0xE8:
            rel = c[ip + 1] | (c[ip + 2] << 8)
            if rel >= 0x8000:
                rel -= 0x10000
            self.push16(self.ip + 3)
            self.ip = (self.ip + 3 + rel) & 0xFFFF
            return True
        if op == 0xC3:
            self.ip = self.pop16()
            return True
        if op == 0xCB:
            self.ip = self.pop16()
            self.seg["cs"] = self.pop16()
            return True
        if op in (0x74, 0x75, 0x72, 0x73, 0x76, 0x77, 0x7C, 0x7D, 0x7E, 0x7F):
            return self.jcc(op)
        if op in (0x04, 0x0C, 0x24, 0x2C, 0x34, 0x3C, 0xA8):
            imm = c[ip + 1]
            if op == 0xA8:
                r = self.r8("al") & imm
                self.zf = 1 if r == 0 else 0
                self.sf = 1 if r & 0x80 else 0
            else:
                cur = self.r8("al")
                self.s8("al", self.arith8({0x04: 0x00, 0x0C: 0x08, 0x24: 0x20, 0x2C: 0x28, 0x34: 0x30, 0x3C: 0x38}[op], cur, imm))
            self.ip += 2
            return True
        if op in (0x05, 0x0D, 0x25, 0x2D, 0x35, 0x3D, 0xA9):
            imm = c[ip + 1] | (c[ip + 2] << 8)
            if imm >= 0x8000:
                imm -= 0x10000
            if op == 0xA9:
                r = self.regs["ax"] & (imm & 0xFFFF)
                self.zf = 1 if r == 0 else 0
                self.sf = 1 if r & 0x8000 else 0
            else:
                cur = self.regs["ax"]
                self.regs["ax"] = self.arith({0x05: 0x01, 0x0D: 0x09, 0x25: 0x21, 0x2D: 0x29, 0x35: 0x31, 0x3D: 0x39}[op], cur, imm)
            self.ip += 3
            return True
        if op in (0x8B, 0x8A, 0x89, 0x88, 0x8E, 0xC4, 0x8D, 0x01, 0x03, 0x29, 0x2B, 0x21, 0x23,
                  0x09, 0x0B, 0x31, 0x33, 0x39, 0x3B, 0x85, 0x81, 0x83, 0x80, 0xD0, 0xD1, 0xD2,
                  0xD3, 0xF7, 0xF6, 0xFF, 0xFE, 0x00, 0x02, 0x28, 0x2A, 0x20, 0x22, 0x08, 0x0A,
                  0x30, 0x32, 0x38, 0x3A):
            return self.modrm(op)
        if op == 0x2E:
            self.ip += 1
            op2 = c[self.ip]
            if op2 in (0x8B, 0xFF):
                return self.modrm(op2)
            return True
        return False


def decode_with_game_decoder(data: bytes) -> bytes:
    """使用 OPEN.EXE 0x1C81 例程(经 8086 模拟)解码 data, 返回输出缓冲区。"""
    code = open(OPEN_EXE, "rb").read()[512:]
    cpu = CPU(code)
    cpu.seg["ss"] = 0x4000
    cpu.regs["sp"] = 0x8000
    cpu.seg["ds"] = cpu.seg["es"] = 0x2000
    # 第一张图只消耗前几百字节; 输入段 64KB 内足够, 避免 8086 段回绕
    cpu.load(0x2000, 0, data[:4096])
    cpu.push16(0x3000)
    cpu.push16(0)
    cpu.push16(0x2000)
    cpu.push16(0x1000)
    cpu.push16(0xFFFF)
    cpu.run(0x1C81, max_steps=2_000_000)
    outlen = min(((cpu.max_di >> 1) * 3 + 12), 500000)
    return bytes(cpu.rdb(0x3000, i) for i in range(outlen))


def render_planes(buf: bytes, rows: int, row_bytes: int, scale: int = 2) -> Image.Image:
    """3 位平面 -> 8 像素/3 字节。"""
    cells = row_bytes // 3
    W = cells * 8
    img = Image.new("RGB", (W, rows))
    px = []
    for r in range(rows):
        row = buf[r * row_bytes : (r + 1) * row_bytes]
        for g in range(cells):
            cell = row[g * 3 : g * 3 + 3]
            for i in range(8):
                v = 0
                for p in range(3):
                    v |= ((cell[p] >> (7 - i)) & 1) << p
                px.append(PAL8[v])
    img.putdata(px)
    if scale != 1:
        img = img.resize((W * scale, rows * scale), Image.NEAREST)
    return img


def render_grpdata_rule(src: bytes, w: int) -> Image.Image:
    """san2/GRPDATA 规则解码(参考), 输出像素流。"""
    import io

    data = io.BytesIO(src)
    out = bytearray()
    while data.tell() < len(src) and len(out) < 4_000_000:
        b1 = data.read(1)[0]
        if b1 & 0x80:
            rs = (b1 & 0x0F) + 1
            ro = ((b1 & 0x30) >> 4) + 1
            ro = ro * w if (b1 & 0x40) else ro * 4
            if len(out) < ro:
                break
            for _ in range(rs * 4):
                out.append(out[-ro])
        else:
            b2 = data.read(1)[0]
            cnt = ((b1 & 0xF0) >> 4) + 1
            buf = []
            bb1, bb2 = b1, b2
            for _ in range(4):
                d = ((bb1 & 0x08) >> 1) | ((bb2 & 0x80) >> 6) | ((bb2 & 0x08) >> 3)
                buf.append(d)
                bb1 = (bb1 << 1) & 0xFF
                bb2 = (bb2 << 1) & 0xFF
            out.extend(buf * cnt)
    n = len(out)
    h = n // w
    img = Image.new("RGB", (w, h))
    img.putdata([PAL8[v] for v in out[: w * h]])
    return img


def main():
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)
    b = open(sys.argv[1] if len(sys.argv) > 1 else PACK, "rb").read()
    w1, w2 = struct.unpack_from("<HH", b, 0)
    print(f"文件头: w1={w1} w2={w2}  文件大小 {len(b)}")
    print("用游戏自身 NPK 解压例程 (OPEN.EXE 0x1C81) 解码第一张图 ...")
    buf = decode_with_game_decoder(b)
    print(f"输出缓冲区: {len(buf)} 字节")
    img = render_planes(buf, 168, 96, 2)
    img.save(os.path.join(outdir, "packdata_256x168_planes.png"))
    print("已保存 packdata_256x168_planes.png")
    # 参考: GRPDATA 规则全流解码
    img2 = render_grpdata_rule(b[4:], 310)
    img2.resize((310, max(1, img2.height * 310 // img2.width)), Image.NEAREST).save(
        os.path.join(outdir, "packdata_grpdata_w310_strip.png")
    )
    print("已保存 packdata_grpdata_w310_strip.png")


if __name__ == "__main__":
    main()
