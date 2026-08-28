#!/usr/bin/env python3
"""
OPENGRP.DAT -- 三国志III (DOS, KOEI 1992) 开场图形数据解析器

格式（2026-08 逆向）：
  文件 = 768 字节头（全 0）+ 5 张图像，共 111,768 字节。
      图 1-4: 320x200，各 24,000 字节 (64,000 像素)
      图 5:   200x200，15,000 字节 (40,000 像素)
  像素均为 3 bit/像素（8 色），位平面存储：
      每 3 字节 -> 8 个像素，像素 i 取三字节第 i 位的组合。
  内容为开场（OPEN.EXE）使用的剧情图文：故事文字屏 + 大图/标题素材。

用法:
  python decode_opengrp.py <OPENGRP.DAT> <输出目录>
"""

import os
import sys

from PIL import Image

PALETTE = [
    (0x00, 0x00, 0x00),
    (0x10, 0xB2, 0x51),
    (0xF3, 0x51, 0x00),
    (0xF3, 0xE3, 0x00),
    (0x00, 0x41, 0xF3),
    (0x00, 0xC3, 0xF3),
    (0xF3, 0x51, 0xD3),
    (0xF3, 0xF3, 0xF3),
]

HEADER = 768
IMAGES = [
    (320, 200, 24000),
    (320, 200, 24000),
    (320, 200, 24000),
    (320, 200, 24000),
    (200, 200, 15000),
]


def decode_3bpp(data: bytes) -> list[int]:
    out = []
    for i in range(0, len(data) - 2, 3):
        g0, g1, g2 = data[i], data[i + 1], data[i + 2]
        for j in range(8):
            bit = 1 << (7 - j)
            out.append(
                ((g0 & bit) != 0) << 2
                | ((g1 & bit) != 0) << 1
                | ((g2 & bit) != 0)
            )
    return out


def render(data: bytes, w: int, h: int, scale: int = 1) -> Image.Image:
    px = decode_3bpp(data)[: w * h]
    img = Image.new("RGB", (w, h))
    img.putdata([PALETTE[v] for v in px])
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

    if len(data) != HEADER + sum(s for _, _, s in IMAGES):
        print(
            f"警告: 文件大小 {len(data)} 与预期 "
            f"{HEADER + sum(s for _, _, s in IMAGES)} 不符"
        )

    off = HEADER
    for i, (w, h, size) in enumerate(IMAGES):
        img = render(data[off : off + size], w, h, scale=2)
        fname = f"opengrp_{i + 1}_{w}x{h}.png"
        img.save(os.path.join(outdir, fname))
        nz = sum(1 for v in decode_3bpp(data[off : off + size])[: w * h] if v)
        print(f"图 {i + 1}: {w}x{h} @ offset {off}  非空像素 {nz}  -> {fname}")
        off += size

    # 汇总大图
    sheet = Image.new("RGB", (320 * 2 + 12, 200 * 2 * 4 + 200 * 2 + 30), (45, 45, 45))
    y = 0
    for i in range(4):
        im = render(data[HEADER + i * 24000 : HEADER + (i + 1) * 24000], 320, 200, scale=2)
        sheet.paste(im, (6, y + 6))
        y += 400
    im5 = render(data[HEADER + 4 * 24000 : HEADER + 4 * 24000 + 15000], 200, 200, scale=2)
    sheet.paste(im5, (6, y + 6))
    sheet.save(os.path.join(outdir, "opengrp_all.png"))
    print("已保存: opengrp_1..5 + opengrp_all.png")


if __name__ == "__main__":
    main()
