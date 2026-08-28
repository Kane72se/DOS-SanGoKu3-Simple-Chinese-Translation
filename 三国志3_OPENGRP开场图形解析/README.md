# 三国志3 OPENGRP.DAT 开场图形解析

## 概述 / Overview

**中文**：`OPENGRP.DAT`（111,768 字节）是 DOS 版《三国志3》（光荣 KOEI，1992）的**开场画面图形数据**，由开场程序 `OPEN.EXE` 加载（KOEI.COM 依次运行 OPEN → MAIN → END）。内容为开场剧情使用的图文：故事文字画面 + 标题/横幅大图，共 5 张图（4 张 320×200 + 1 张 200×200）。

**English**: `OPENGRP.DAT` (111,768 bytes) holds the opening-sequence graphics of the DOS *Romance of the Three Kingdoms III* (KOEI, 1992), loaded by the intro program `OPEN.EXE`. It contains 5 images (four 320×200 screens plus one 200×200 graphic) used for the opening story text and title/banner art.

---

## 文件结构 / File Layout

```
768 字节头部（全 0）+ 5 张图像 = 111,768 字节
  图 1-4: 320x200   各 24,000 字节 (64,000 像素)
  图 5:   200x200   15,000 字节 (40,000 像素)
```

像素为 **3 bit/像素（8 色）**，采用光荣早期位平面存储：每 3 字节表示 8 个像素，像素 i 由三字节第 i 位的组合而成（与 `KAODATA.DAT` / `GRPDATA.DAT` / `MONTAGE.DAT` 相同）。

## 调色板 / Palette

| 索引 | RGB | 索引 | RGB |
|---:|---|---:|---|
| 0 | 黑 #000000 | 4 | 蓝 #0041F3 |
| 1 | 绿 #10B251 | 5 | 青 #00C3F3 |
| 2 | 橙红 #F35100 | 6 | 品红 #F351D3 |
| 3 | 黄 #F3E300 | 7 | 白 #F3F3F3 |

---

## 渲染结果 / Rendered Output

![OPENGRP 全部画面](opengrp_all.png)

![开场画面1](opengrp_1_320x200.png)

![开场画面4](opengrp_4_320x200.png)

![过场/结尾图5](opengrp_5_200x200.png)

单张图：`opengrp_1..3_320x200.png`（故事文字屏）、`opengrp_4_320x200.png`（大幅装饰图形画面）、`opengrp_5_200x200.png`（方形图）。

## 使用方法 / Usage

```bash
python decode_opengrp.py <OPENGRP.DAT 路径> <输出目录>
```

依赖：Python 3 + Pillow。

---

## 参考 / References

- 格式与同目录 `KOEI.DAT`（48,768 字节 = 768 头 + 2×24,000，KOEI logo 画面）一致，字节数精确吻合 320×200 显示模式。
- 位平面 3bpp 解码：与 [tzengyuxio/kaodata](https://github.com/tzengyuxio/kaodata) 项目 `dekoei/utils.py` 的 `to_3bpp_indexes` 一致。
