#!/usr/bin/env python3
"""
MAPDATA.DAT -- 三国志III (DOS, KOEI 1992) 地图数据解析器（研究版）

现状（2026-08 逆向）：
  文件 = 4 字节头 (宽 u16 LE=640, 高 u16 LE=135) + KOEI NPK 式压缩流。
  压缩 token 结构与 GRPDATA.DAT 相同（高位置 1 = 回拷；否则为 2 字节字面量，
  每次展开 4 像素），但像素位深尚未最终确定：
    - 3bpp 位组合 -> 8 色（与 GRPDATA 相同公式）
    - 4bpp 位组合 -> 16 色（与大地图截图的 15 色接近）
  整条流解出 1,758,996 像素。压缩流内"行回拷"使用的行宽 <= 32，
  说明数据按 32px 宽的行/图块组织，但最终显示宽度未定
  （脚本提供多种宽度/竖条重组渲染，供人工辨认）。

用法:
  python decode_mapdata.py <MAPDATA.DAT> <输出目录> [--bpp 3|4] [--width 640|960|1280]
"""

import argparse
import io
import os
import struct
import sys

from PIL import Image


def koei_unpack(src: bytes, width: int, bpp: int) -> bytes:
    """KOEI NPK 式解压；bpp=3 用 GRPDATA 公式，bpp=4 用扩展公式。"""
    data = io.BytesIO(src)
    out = bytearray()
    while data.tell() < len(src):
        b = data.read(1)[0]
        if b & 0x80:
            rs = ((b & 0x0F) + 1)
            ro = ((b & 0x30) >> 4) + 1
            ro = ro * width if (b & 0x40) else ro * 4
            if len(out) < ro:
                return bytes(out)
            for _ in range(rs * 4):
                out.append(out[-ro])
        else:
            b1 = b
            b2 = data.read(1)[0]
            cnt = ((b1 & 0xF0) >> 4) + 1
            buf = []
            for _ in range(4):
                if bpp == 3:
                    d = ((b1 & 0x08) >> 1) | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3)
                else:
                    d = ((b1 & 0x80) >> 4) | ((b1 & 0x08) >> 1) | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3)
                buf.append(d)
                b1 = (b1 << 1) & 0xFF
                b2 = (b2 << 1) & 0xFF
            out.extend(buf * cnt)
    return bytes(out)


PAL3 = [
    (0, 0, 0), (0x10, 0xB2, 0x51), (0xF3, 0x51, 0x00), (0xF3, 0xE3, 0x00),
    (0x00, 0x41, 0xF3), (0x00, 0xC3, 0xF3), (0xF3, 0x51, 0xD3), (0xF3, 0xF3, 0xF3),
]

# 大地图截图（v10_大地图_休养.png / 游戏内截图）提取的 16 色
PAL16 = [
    (0, 0, 0), (0, 16, 81), (32, 113, 16), (146, 162, 81),
    (211, 130, 97), (195, 195, 130), (243, 81, 0), (243, 243, 243),
    (100, 33, 0), (0, 9, 44), (139, 46, 0), (89, 40, 51),
    (227, 130, 0), (16, 178, 81), (0, 65, 243), (243, 227, 0),
]


def render(dec: bytes, w: int, h: int, pal) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([pal[v % len(pal)] for v in dec[: w * h]])
    return img


def reassemble(dec: bytes, nstrips: int, strip_h: int) -> bytes:
    """把 32px 宽的竖条流重组为 nstrips*32 宽的图（假设模型）。"""
    w = nstrips * 32
    out = bytearray(w * strip_h)
    for s in range(nstrips):
        base = s * strip_h * 32
        for y in range(strip_h):
            out[y * w + s * 32 : y * w + s * 32 + 32] = dec[base + y * 32 : base + y * 32 + 32]
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("outdir")
    ap.add_argument("--bpp", type=int, default=4)
    ap.add_argument("--width", type=int, default=640)
    args = ap.parse_args()

    data = open(args.file, "rb").read()
    w0, h0 = struct.unpack("<HH", data[0:4])
    print(f"头: {w0}x{h0}")

    os.makedirs(args.outdir, exist_ok=True)
    dec = koei_unpack(data[4:], 32, args.bpp)
    print(f"解出 {len(dec)} 像素，{len(set(dec))} 种值")

    pal = PAL3 if args.bpp == 3 else PAL16
    n = len(dec)
    if args.width == 0:
        # 竖条重组模式：同时输出 20/30/40 条
        for nstrips, strip_h in [(20, 2748), (30, 1832), (40, 1374)]:
            px = reassemble(dec, nstrips, strip_h)
            w = nstrips * 32
            render(px, w, strip_h, pal).save(os.path.join(args.outdir, f"strips{nstrips}_{w}x{strip_h}.png"))
    else:
        w = args.width
        h = n // w
        render(dec, w, h, pal).save(os.path.join(args.outdir, f"w{w}_h{h}.png"))
        if h >= 400:
            render(dec, w, 400, pal).save(os.path.join(args.outdir, f"w{w}_screen1.png"))
    print("完成")


if __name__ == "__main__":
    main()
