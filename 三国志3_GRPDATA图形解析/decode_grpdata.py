#!/usr/bin/env python3
"""
GRPDATA.DAT -- 三国志III (DOS, KOEI 1992) 界面图形数据解析器

格式（与三国志II 的 GRPDATA.DAT 相同，由 kaodata 项目确认）：
  每张图 = 4 字节头 (宽 u16 LE, 高 u16 LE) + KOEI NPK 式压缩数据
  像素为 3 bit/像素（8 色），压缩流 token 说明见下方 dec_scanline。

用法:
  python decode_grpdata.py <GRPDATA.DAT> <输出目录>
"""

import io
import os
import struct
import sys

from PIL import Image

# 三国志III DOS 实际使用的 8 色调色板（已与游戏内截图逐一核对）
PALETTE = [
    (0x00, 0x00, 0x00),  # 0 黑
    (0x10, 0xB2, 0x51),  # 1 绿
    (0xF3, 0x51, 0x00),  # 2 橙红
    (0xF3, 0xE3, 0x00),  # 3 黄
    (0x00, 0x41, 0xF3),  # 4 蓝
    (0x00, 0xC3, 0xF3),  # 5 青
    (0xF3, 0x51, 0xD3),  # 6 品红
    (0xF3, 0xF3, 0xF3),  # 7 白
]


def koei_unpack(src: bytes, width: int, limit: int | None = None) -> bytes:
    """解压 KOEI NPK 式 3bpp 图像流。

    token 规则（字节 b）:
      b & 0x80 : 回拷。长度 = ((b & 0x0F) + 1) * 4 像素；
                 偏移 = (((b & 0x30) >> 4) + 1) * 4 字节，
                 若 b & 0x40 则偏移改为 * width（整行）。
      否则     : 字面量。读第二个字节 b2；
                 重复 ((b1 & 0xF0) >> 4) + 1 次，
                 每次从 b1/b2 的连续 4 个位组合出 4 个像素。
    """
    data = io.BytesIO(src)
    out = bytearray()
    while data.tell() < len(src) and (limit is None or len(out) < limit):
        b = data.read(1)[0]
        if b & 0x80:
            run_size = ((b & 0x0F) + 1)
            run_offset = ((b & 0x30) >> 4) + 1
            run_offset = run_offset * width if (b & 0x40) else run_offset * 4
            for _ in range(run_size * 4):
                out.append(out[-run_offset])
        else:
            b1 = b
            b2 = data.read(1)[0]
            count = ((b1 & 0xF0) >> 4) + 1
            buf = []
            for _ in range(4):
                d = ((b1 & 0x08) >> 1) | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3)
                buf.append(d)
                b1 = (b1 << 1) & 0xFF
                b2 = (b2 << 1) & 0xFF
            out.extend(buf * count)
    return bytes(out)


def render(pixels: bytes, w: int, h: int, scale: int = 2) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([PALETTE[v] for v in pixels[: w * h]])
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    data = open(sys.argv[1], "rb").read()
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    pos = 0
    index = 0
    while pos + 4 <= len(data):
        w, h = struct.unpack("<HH", data[pos : pos + 4])
        if not (1 <= w <= 1024 and 1 <= h <= 1024):
            print(f"@{pos}: 头非法 w={w} h={h}，停止")
            break
        try:
            px = koei_unpack(data[pos + 4 :], w, w * h)
        except IndexError:
            print(f"@{pos}: 头 w={w} h={h} 无法按本格式解码（可能为其它数据结构），停止")
            break
        print(f"图 {index + 1}: {w}x{h}  起始偏移={pos}  像素={len(px)}")
        # 找到该图实际占用的压缩字节数
        src = io.BytesIO(data[pos + 4 :])
        dest = bytearray()
        while len(dest) < w * h:
            b = src.read(1)[0]
            if b & 0x80:
                rs = ((b & 0x0F) + 1)
                ro = ((b & 0x30) >> 4) + 1
                ro = ro * w if (b & 0x40) else ro * 4
                for _ in range(rs * 4):
                    dest.append(dest[-ro])
            else:
                b2 = src.read(1)[0]
                cnt = ((b & 0xF0) >> 4) + 1
                buf = []
                b1 = b
                for _ in range(4):
                    d = ((b1 & 0x08) >> 1) | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3)
                    buf.append(d)
                    b1 = (b1 << 1) & 0xFF
                    b2 = (b2 << 1) & 0xFF
                dest.extend(buf * cnt)
        used = src.tell()
        render(px, w, h, 4).save(os.path.join(outdir, f"frame_{index + 1:02d}_{w}x{h}.png"))
        print(f"   -> frame_{index + 1:02d}_{w}x{h}.png  压缩体 {used} 字节")
        pos += 4 + used
        index += 1

    print(f"文件尾剩余 {len(data) - pos} 字节")


if __name__ == "__main__":
    main()
