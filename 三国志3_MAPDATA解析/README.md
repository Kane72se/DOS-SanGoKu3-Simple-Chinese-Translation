# 三国志3 MAPDATA.DAT 解析（研究进度）

## 概述 / Overview

**中文**：`MAPDATA.DAT`（99,162 字节）是 DOS 版《三国志3》的地图数据文件，由 `MAIN.EXE` 加载。当前逆向进度：

- 文件头：4 字节 `(宽=640 u16 LE, 高=135 u16 LE)`，随后是 KOEI NPK 式压缩流（token 结构与 `GRPDATA.DAT` 相同：高位置 1 = 回拷，否则为 2 字节字面量、每次展开 4 像素）。
- 整条压缩流可解出 **1,758,996 像素**；压缩流内"行回拷"使用的行宽 ≤ 32，说明数据按 32px 宽的行/图块组织。
- 像素位深有两种候选：**3bpp（8 色，与 GRPDATA 相同公式）** 与 **4bpp（16 色，扩展公式）**。4bpp 解出 16 种值，与大地图截图（整屏恰 15 色）更接近。
- **尚未最终确认**：显示宽度（640 直排 / 竖条重组 960 / 1280 等）、16 色调色板的索引映射。为此保留多种渲染图，供后续人工辨认或继续逆向。

**English**: `MAPDATA.DAT` (99,162 bytes) is the map data of the DOS *Romance of the Three Kingdoms III*, loaded by `MAIN.EXE`. Progress so far:

- 4-byte header `(width=640 u16 LE, height=135 u16 LE)` + a KOEI NPK-style compressed stream (same token scheme as `GRPDATA.DAT`).
- The stream decompresses to **1,758,996 pixels**; its row-backreference width is ≤ 32, so data is organized in 32-px-wide rows/tiles.
- Two pixel-depth candidates: **3 bpp (8 colors, GRPDATA formula)** and **4 bpp (16 colors, extended formula)**. The 16-color decode matches the map screen screenshot (15 distinct colors on screen).
- **Not yet finalized**: display width (640 direct / strip-reassembly 960 / 1280 etc.) and the exact 16-color palette mapping. Multiple renders are kept for visual identification or further RE work.

---

## 文件结构 / File Layout

| 偏移 | 内容 |
|---|---|
| 0 | `80 02` = 640（宽，u16 LE） |
| 2 | `87 00` = 135（高，u16 LE） |
| 4 .. EOF | KOEI NPK 式压缩流（99,158 字节） |

压缩 token（与 GRPDATA 相同）：

- `b & 0x80`：**回拷**。长度 = `((b & 0x0F) + 1) * 4` 像素；偏移 = `(((b & 0x30) >> 4) + 1) * 4` 字节，若 `b & 0x40` 则偏移 × 行宽（行回拷）。
- 否则：**字面量**。读 `b2`，重复 `((b & 0xF0) >> 4) + 1` 次，每次按位组合展开 4 像素（3bpp / 4bpp 公式见 `decode_mapdata.py`）。

---

## 渲染图 / Renders

`渲染图/` 目录包含 3bpp / 4bpp、直排与竖条重组、以及按大地图截图配色的多组输出，供辨认与后续逆向。

## 使用方法 / Usage

```bash
python decode_mapdata.py <MAPDATA.DAT> <输出目录> [--bpp 3|4] [--width 640|960|1280]
python decode_mapdata.py <MAPDATA.DAT> <输出目录> --width 0   # 竖条重组模式
```

---

## 参考 / References

- 压缩格式与 [GRPDATA.DAT 解析](../三国志3_GRPDATA图形解析/README.md) 同族（KOEI NPK 式）。
- 大地图截图配色取自仓库内 `三国志3_简体化_全量逆向/v10_大地图_休养.png` 及游戏内截图。
