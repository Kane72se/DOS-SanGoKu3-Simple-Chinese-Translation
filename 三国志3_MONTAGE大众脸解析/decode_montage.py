#!/usr/bin/env python3
"""
MONTAGE.DAT -- 三国志III (DOS, KOEI 1992) 大众脸拼装素材库解析器

格式（2026-08 逆向，对照 PTT yuxio《三国志3 大众脸脸谱研究》验证）：
  文件 = 11 个框架组 × 12672 字节，共 139392 字节。
  每个框架组（= 一种框架造型，前 7 组武官 / 后 4 组文官）内含 20 个部件：
      4 个上半部   64x36  864 B   (offset 0, 864, 1728, 2592)
      4 个下半部   64x44 1056 B   (offset 3456, 4512, 5568, 6624)
      6 个眼睛部件 64x16  384 B   (offset 7680 + i*384)
      2 个鼻子部件 64x16  384 B   (offset 9984 + i*384)
      4 个嘴巴部件 64x20  480 B   (offset 10752 + i*480)
  像素均为 3 bit/像素（8 色），位平面存储：
      每 3 字节 -> 8 个像素，像素 i 取三字节第 i 位的组合。
  游戏按「上半 + 下半 + 眼 + 鼻 + 口」拼出 64x80 的大众脸
  （上半 36px + 下半 44px），面值大于 307 时启用。

用法:
  python decode_montage.py <MONTAGE.DAT> <输出目录>
"""

import os
import sys

from PIL import Image, ImageDraw

# 三国志III DOS 实际使用的 8 色调色板（与 KAODATA.DAT / GRPDATA.DAT 相同）
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

GROUP_BYTES = 12672
FRAME_GROUPS = 11

UPPER = (864, 64, 36, 4)     # bytes, w, h, count
LOWER = (1056, 64, 44, 4)
EYE = (384, 64, 16, 6)
NOSE = (384, 64, 16, 2)
MOUTH = (480, 64, 20, 4)

# name -> (bytes, w, h, count, group内偏移)
PARTS = {
    "upper": (*UPPER, 0),
    "lower": (*LOWER, 3456),
    "eye": (*EYE, 7680),
    "nose": (*NOSE, 7680 + 6 * 384),
    "mouth": (*MOUTH, 7680 + 6 * 384 + 2 * 384),
}


def decode_3bpp(data: bytes) -> list[int]:
    """3 byte -> 8 pixel 位平面解码，返回像素索引列表。"""
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


def render_part(data: bytes, w: int, h: int) -> Image.Image:
    px = decode_3bpp(data)[: w * h]
    img = Image.new("RGB", (w, h))
    img.putdata([PALETTE[v] for v in px])
    return img


def parse_parts(data: bytes) -> dict[str, list[Image.Image]]:
    """按 11 个框架组解析出全部部件图像。"""
    all_parts = {name: [] for name in PARTS}
    for g in range(FRAME_GROUPS):
        base = g * GROUP_BYTES
        for name, (size, w, h, cnt, off) in PARTS.items():
            for i in range(cnt):
                part_off = base + off + i * size
                all_parts[name].append(
                    render_part(data[part_off : part_off + size], w, h)
                )
    return all_parts


def paste_grid(
    images: list[Image.Image],
    cols: int,
    cell_w: int,
    cell_h: int,
    pad: int = 4,
    label: str = "",
) -> Image.Image:
    rows = (len(images) + cols - 1) // cols
    W = cols * cell_w + (cols + 1) * pad
    H = rows * cell_h + (rows + 1) * pad + (22 if label else 0)
    canvas = Image.new("RGB", (W, H), (40, 40, 40))
    d = ImageDraw.Draw(canvas)
    if label:
        d.text((pad, 3), label, fill=(240, 240, 240))
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = (22 if label else 0) + pad + r * (cell_h + pad)
        canvas.paste(img, (x, y))
        idx = Image.new("RGB", (cell_w, 12), (40, 40, 40))
        ImageDraw.Draw(idx).text((0, 0), str(i + 1), fill=(200, 200, 200))
        canvas.paste(idx, (x, y + cell_h))
    return canvas


def assemble_face(
    parts: dict[str, list[Image.Image]],
    frame: int,
    upper_i: int = 0,
    lower_i: int = 0,
    eye_i: int = 0,
    nose_i: int = 0,
    mouth_i: int = 0,
) -> Image.Image:
    """按游戏规则拼一张 64x80 大众脸。"""
    # 每框架组 4 个上半/下半、6 眼、2 鼻、4 口（均为该框架专属）
    upper = parts["upper"][frame * 4 + upper_i]
    lower = parts["lower"][frame * 4 + lower_i]
    eye = parts["eye"][frame * 6 + eye_i]
    nose = parts["nose"][frame * 2 + nose_i]
    mouth = parts["mouth"][frame * 4 + mouth_i]

    # 绘制顺序：五官(眼/鼻/口) -> 上半部(帽子/盔) -> 下半部(脸/须/肩)
    # 框架自带的正面部区域为不透明时，会盖住其下的通用五官；
    # 武官框架上半部脸部留空，露出通用五官。
    canvas = Image.new("RGB", (64, 80), (0, 0, 0))
    canvas.paste(eye, (0, 18))
    canvas.paste(nose, (0, 32))
    canvas.paste(mouth, (0, 48))
    canvas.paste(upper, (0, 0))
    canvas.paste(lower, (0, 36))
    return canvas


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    data = open(sys.argv[1], "rb").read()
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    if len(data) != FRAME_GROUPS * GROUP_BYTES:
        print(f"警告: 文件大小 {len(data)} 与预期 {FRAME_GROUPS * GROUP_BYTES} 不符")

    parts = parse_parts(data)
    total = sum(len(v) for v in parts.values())
    print(f"解析出 {total} 个部件: " + ", ".join(f"{k} {len(v)}" for k, v in parts.items()))

    # 1) 上半部 11x4
    paste_grid(parts["upper"], 4, 64, 36, label="Upper (upper half) x4 per frame").save(
        os.path.join(outdir, "montage_upper.png")
    )
    # 2) 下半部 11x4
    paste_grid(parts["lower"], 4, 64, 44, label="Lower (lower half) x4 per frame").save(
        os.path.join(outdir, "montage_lower.png")
    )
    # 3) 五官部件
    feats = []
    for name in ["eye", "nose", "mouth"]:
        _, w, h, cnt, _ = PARTS[name]
        img = paste_grid(parts[name], cnt, w, h, label=name)
        feats.append(img)
    # 并排
    total_w = sum(im.width for im in feats) + 4 * (len(feats) + 1)
    max_h = max(im.height for im in feats)
    sheet = Image.new("RGB", (total_w, max_h), (40, 40, 40))
    x = 4
    for im in feats:
        sheet.paste(im, (x, 0))
        x += im.width + 4
    sheet.save(os.path.join(outdir, "montage_features.png"))

    # 4) 各框架示例脸（每个框架拼 1 张）
    faces = [
        assemble_face(parts, g, 0, 0, 0, 0, 0).resize((128, 160), Image.NEAREST)
        for g in range(FRAME_GROUPS)
    ]
    paste_grid(faces, 11, 128, 160, label="Sample assembled faces (one per frame)").save(
        os.path.join(outdir, "montage_sample_faces.png")
    )

    # 5) 汇总大图：11 个框架组，每组 4 上半 + 4 下半；底部五官
    pad = 6
    label_h = 22
    cell_h = max(36, 44)
    W = 8 * 64 + 9 * pad
    H = label_h + 11 * (cell_h + 12 + pad) + label_h + (16 + 12 + pad) * 4
    sheet = Image.new("RGB", (W, H), (45, 45, 45))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 3), "MONTAGE.DAT parts: 11 frames x (4 upper + 4 lower) + 6 eyes + 2 noses + 4 mouths", fill=(255, 255, 255))
    for g in range(11):
        y0 = label_h + g * (cell_h + 12 + pad)
        d.text((pad, y0 + 1), f"F{g + 1:02d}", fill=(255, 255, 128))
        for i, name in enumerate(["upper"] * 4 + ["lower"] * 4):
            img = parts[name][g * 4 + (i % 4)]
            x = pad + (i + 1) * pad + i * 64
            sheet.paste(img, (x, y0 + 14))
    d.text((pad, label_h + 11 * (cell_h + 12 + pad) + 2), "Shared features (eyes / noses / mouths)", fill=(255, 255, 128))
    y0 = label_h + 11 * (cell_h + 12 + pad) + label_h
    for name, cnt in [("eye", 6), ("nose", 2), ("mouth", 4)]:
        _, w, h, _, _ = PARTS[name]
        d.text((pad, y0 + 1), f"{name} x{cnt}", fill=(200, 200, 200))
        for i in range(cnt):
            img = parts[name][i]
            x = pad + (i + 1) * pad + i * w
            sheet.paste(img, (x, y0 + 14))
        y0 += 16 + 12 + pad
    sheet.save(os.path.join(outdir, "montage_all.png"))
    print("已保存: montage_upper.png / montage_lower.png / montage_features.png / montage_sample_faces.png / montage_all.png")


if __name__ == "__main__":
    main()
