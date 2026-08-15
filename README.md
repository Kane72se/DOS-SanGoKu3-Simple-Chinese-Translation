# DOS 三国志3 繁体中文 → 简体中文 字库替换 + 存档/剧本修改器
# DOS Romance of the Three Kingdoms III (SanGoKu3) Traditional→Simplified Chinese Font Patch & Save/Scenario Editor

## 项目简介 / Overview

**中文**：本项目针对 DOS 版《三国志3》（光荣 KOEI，繁体中文版）做简体化处理，并附带一个功能完整的存档/剧本修改器。

- 简体化采用「字模替换」方案：不改游戏文本编码、不改程序代码，只重建 `HAN.16P` 字库中的 16×14 点阵字形。游戏仍以 BIG5 读取文本，但显示的是简体字形。
- 字库共 1335 个槽位 × 28 字节（16×14 点阵），已全部完成槽位→汉字映射（`槽位映射表v22.tsv`，无未知槽位）。
- 修改器基于 Python 3 + tkinter，可编辑武将能力/兵力/宝物/忠诚/寿命等隐藏属性，以及城市数值（人口、金、军粮、开发、商业等），支持剧本同步。

**English**: This project localizes the DOS version of *Romance of the Three Kingdoms III* (KOEI, Traditional Chinese release) to Simplified Chinese, and ships with a full-featured save/scenario editor.

- The localization uses **glyph replacement**: game text encoding and program code are untouched; only the 16×14 dot-matrix glyphs inside `HAN.16P` are rebuilt. The game still reads BIG5 text, but displays Simplified glyphs.
- The font contains 1335 slots × 28 bytes (16×14). The complete slot→character map is provided (`槽位映射表v22.tsv`, zero unknown slots).
- The editor is Python 3 + tkinter, supporting officer abilities/troops/items/loyalty/lifespan (hidden stats), plus city data (population, gold, food, development, commerce, etc.), with scenario sync.

---

## 目录结构 / Repository Layout

```
├─ README.md                                  本说明（中英双语）
├─ san3_简体化_第一阶段/                     第一阶段成果（HAN.16P 示例 + 主菜单对比截图）
│   ├─ HAN.16P                               繁体原版字库（备份参考）
│   ├─ 主菜单_繁体原版.png
│   ├─ 主菜单_简体化后.png
│   └─ 说明.md
├─ san3_简体化_全量逆向/                     全量简体化最终成果（推荐使用 v22）
│   ├─ HAN.16P_全量v22版                      ★ 最终字库：直接替换游戏目录 HAN.16P
│   ├─ 槽位映射表v22.tsv                     ★ 1335 槽位 → 汉字 全量映射（0 未知）
│   ├─ HAN.16P_全量v4~v21版                  历史版本字库（演进记录）
│   ├─ 槽位映射表v4~v21.tsv                  历史版本映射表
│   ├─ v16~v22更新说明.md                    各版本修复说明
│   ├─ 说明.md / 全量解码进展v8.md / 动态反编译可行性报告.md / 数值与数据结构笔记.md
│   ├─ captured_pairs.tsv                    运行时捕获的槽位→字符码记录
│   ├─ 运行时槽位字符码表.bin                full_table.bin（程序内部码表）
│   └─ 主菜单/剧本选择/君主选择 等验证截图
├─ 三国志3修改器/                             ★ 修改器
│   ├─ 三国志3修改器.py                      主程序（pythonw 运行）
│   ├─ full_table.bin                        与字库配套的内部码→槽位表
│   ├─ han_map_v20.tsv                       槽位→汉字映射（修改器显示/搜索用）
│   ├─ 宝物列表.txt                          宝物 ID→名称（可自行编辑）
│   └─ 使用说明.txt
├─ 三国志3武将列表_简体对照v4.xlsx           武将名/能力对照表（含简繁对照列）
└─ 武将名简体化_思路与基础数据.md            武将名字体化定位思路与数据说明
```

---

## 简体化使用方法 / How to Apply the Simplified Font

**中文**：

1. 备份游戏目录下的 `HAN.16P`（恢复繁体版时直接还原即可）。
2. 把 `san3_简体化_全量逆向/HAN.16P_全量v22版` 复制到游戏目录，重命名为 `HAN.16P`。
3. 用 DOSBox / DOSBox-X 运行 `PLAY.BAT` 即可。推荐画面输出 `opengl perfect`，保持 4:3 比例，避免字形拉伸。

**English**:

1. Back up `HAN.16P` in the game directory (restore it to revert to Traditional).
2. Copy `san3_简体化_全量逆向/HAN.16P_全量v22版` into the game folder and rename it to `HAN.16P`.
3. Run `PLAY.BAT` under DOSBox / DOSBox-X. Recommended video output: `opengl perfect`, keep 4:3 aspect ratio to avoid stretched glyphs.

> 只替换字形，不改文本字节，因此**旧存档可正常读取**，且不影响 NBDATA.DAT（武将名数据）、NAME.16P 或图片内嵌字。
> Only glyphs are replaced; text bytes are unchanged, so **existing saves load fine**, and NBDATA.DAT (officer names), NAME.16P, and bitmap-embedded text are unaffected.

---

## 修改器使用方法 / How to Use the Editor

**中文**：

- 需要 Python 3（含 tkinter）与 `zhconv` 库：`pip install zhconv`
- 运行：`pythonw 三国志3修改器.py`（或 `python 三国志3修改器.py`）
- 程序同目录需放 `full_table.bin`、`han_map_v20.tsv`、`宝物列表.txt`
- 打开文件：
  - `打开存档 SANGOKU3.SAV`：游戏存档（自动定位武将数据块，自动匹配同目录剧本）
  - `打开剧本`：仅接受 `SNDATA1B.CIM ~ SNDATA6B.CIM`（六剧本武将数据）
  - `打开城市剧本`：仅接受 `SNDATA1.CIM ~ SNDATA6.CIM`（六剧本城市数据）
- 可编辑：兵力、陆指/水指/武力/智力/政治/魅力、忠诚、相性、义理、寿命、野心、冷静、勇猛、运气、疾病、行动、身份、所在、所属、亲族、训练、士气、出生年、工作等；宝物格子（N+1 可增删，含 12+ 件宝物下拉）；城市人口/金/军粮/开发/耕作/灌溉/治水/商业/税率/民忠/弓/强弓/军马/战舰/重舰/轻舰。
- 保存前自动备份 `.bak`。
- 搜索支持简体/繁体/拼音数字编号（按序号）模糊匹配。

**English**:

- Requires Python 3 with tkinter and the `zhconv` package: `pip install zhconv`
- Run: `pythonw 三国志3修改器.py` (or `python 三国志3修改器.py`)
- Keep `full_table.bin`, `han_map_v20.tsv`, and `宝物列表.txt` next to the script.
- File types:
  - `Open Save SANGOKU3.SAV`: game save (auto-locates the officer block, auto-matches scenario files in the same folder)
  - `Open Scenario`: accepts only `SNDATA1B.CIM`–`SNDATA6B.CIM` (six scenario officer files)
  - `Open City Scenario`: accepts only `SNDATA1.CIM`–`SNDATA6.CIM` (six scenario city files)
- Editable: troop strength, land/sea/force/intel/politics/charm, loyalty, compatibility (相性), loyalty (义理), lifespan, ambition, calm, bravery, luck, disease, acted flag, status, location, lord, family, training, morale, birth year, work, etc.; item slots (N+1 with dropdown of 12+ items); city population/gold/food/development/farming/irrigation/flood control/commerce/tax/loyalty/bows/strong bows/horses/warships/heavy ships/light ships.
- Auto-backup `.bak` before saving.
- Search supports Simplified/Traditional names and numeric index.

---

## 技术说明 / Technical Notes

**字库格式 / Font format**

- `HAN.16P`：37380 字节 = 1335 槽位 × 28 字节；每槽 14 行 × 16 像素（每行 2 字节）。
- 简体字形来源：GB2312 `HZK16` 16×16 点阵优先，缺字回退 SimSun 渲染；16 行按“OR 合并”压缩为 14 行，避免上下缺行（v18 起）。

**逆向方法 / Reverse-engineering method**

- 通过 DOSBox-X 调试器动态捕获“字符码→槽位”映射，结合主菜单锚点、武将能力值交叉验证、屏幕像素↔字库字节零误差比对，逐步解出全部 1335 槽位。
- 最终 `槽位映射表v22.tsv` 无未知槽位。

**修改器数据结构 / Editor data structure**

- 武将记录 49 字节；能力六维在偏移 17–22；名字为 `D9 xx` 内部码（配合 `full_table.bin` 解码显示）。
- 城市记录 = [70 字节数据][4 字节名字]，字段偏移已用剧本1陈留初始值核对；人口存值 = 显示值 ÷ 100。
- 宝物以位掩码存储（`0x0432` 等），掩码位 → 宝物 ID。

---

## 版本历史 / Version History

| 版本 | 说明 |
|---|---|
| v4–v14 | 字模替换早期版本，逐步解出锚点与常用字，采用 16 行裁切方式 |
| v16 | 修复 11 处映射表错误（泉→呂、巫→兒、林→樊 等）；新增 39 槽定位 |
| v17 | 追加 110 处错字修正，利用武将能力值交叉验证 |
| v18 | 改为 16 行 OR 压缩成 14 行，解决简体字上下缺行问题 |
| v19 | 首次用「武将数据文件能力值↔武将表」交叉验证，解出 15 未知槽位并修正 110 错字 |
| v20 | 修复 8 个界面字（现/处/去/吗/蓄/隆/死/龙回退），并完成城市/战场名修正 |
| v21 | 修复 號(857)/還(267)/廬(1321)，并补写 着/须/壶/邺 |
| v22 | 由用户辨认补齐最后 37 个未知槽位（含 諜/強/勢/舉/職/認/驃 等），未知槽位清零 |

---

## 已知限制 / Known Limitations

- 部分槽位被原版字库“一字多用”（如 張郃 原版显示“張和”），为忠实还原原版而保留，非 bug。
- 个别超纲简体字（如 𬘭）SimSun 无字形，保留原字形。
- 图片内嵌字（如“變更為”状态栏中的“為”）不属于 HAN 字库，字库替换无法修改。
- 修改器的“能力同步写入剧本”功能仅在打开存档且同目录存在对应 `SNDATAB.CIM` 时可用。

---

## 致谢 / Credits

- PTT yuxio《三國志3代修改》结构说明（数据格式参考）
- KOEI《三国志III》DOS 繁体中文版（素材与游戏本体）
- 社区“補完計畫”修正版字库（早期对照参考）

## License / 许可

本项目仅用于学习与个人使用。游戏本体、图片素材及数据格式的版权归 KOEI / 光荣所有。
