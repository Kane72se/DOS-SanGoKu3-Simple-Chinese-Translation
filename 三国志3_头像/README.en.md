# San3 HD Portrait Overlay — 三国志3_头像

While playing the DOS version of *Romance of the Three Kingdoms III* in DOSBox-X / PCem, this overlay replaces the in-game 64×80, 8-colour officer portraits with the higher-quality 256-colour Windows-version portraits, **in place**.

![Effect: high-res Gongsun Zan overlaid on the PCem portrait](screenshot_PCem_公孙瓒.png)

## Overview
- Works on DOSBox-X, PCem, etc. (matched by window title; multiple targets via a comma-separated list).
- Follows the **matching window that is currently in the foreground**; hides entirely when its target is not in front, so it never covers other windows.
- Replaces **all on-screen portraits at once** (large portraits and small thumbnails), anchored at the top-left, preserving the 4:5 ratio.
- Positioning / size / aspect / scale / content-region offset are **tunable per target (emulator)** in `config.ini`.
- Follows window movement, stretching, and DPI (desktop scaling %).

## Assets (from reverse engineering)
- **DOS** `KAODATA.DAT`: 307 portraits, 64×80, 8 colours; bitplane = 3 bytes per 8 pixels; palette from the official `dekoei/san3.py` fixed 8-colour set.
- **Windows** `FACES.BMP`: 768×4160, 12 columns; index **0–306 = 307 unique faces**, **307–311 = empty slots**, **312–622 = generic faces (311)**; decode skips `[307,308,309,310,311,623]`.
- Both versions' **unique faces share the same order** (index aligned): DOS index i ↔ `FACES.BMP` index i, so no cross-version pixel matching is needed.
- Portrait index ↔ officer name comes from the `顏` field of the `SNDATA#B.CIM` person tables (<307 = unique face; >307 = generic face, not replaced in v1).

## Layout
```
三国志3_头像/
├─ san3overlay.py          main program (transparent always-on-top click-through overlay)
├─ config.ini              config (multi-target / threshold / scale / per-target tuning)
├─ requirements.txt        dependencies
├─ README.md               this guide (Chinese)
├─ README.en.md            English guide (this file)
├─ preview_4people.png     4-officer DOS-vs-WIN comparison
├─ screenshot_PCem_公孙瓒.png  in-game result screenshot
└─ assets/
   ├─ refs/000..306.png    307 DOS reference faces (for template matching)
   ├─ win/000..306.png     307 Windows hi-res faces (for display)
   └─ persons_s1.csv       scenario-1 person table (index ↔ name)
```

## How it works (`san3overlay.py`)
`PrintWindow the emulator window's own content (not the overlay, avoiding self-capture feedback)` → locate the game content region (saturation + largest colour component) → multi-scale (1.0/0.75/0.5) multi-target template matching (coarse on 1/ds, then refine top-k at full resolution) → keep high-score unique faces → draw `win/{idx}.png` scaled at the matched top-left anchor.

## Key notes / pitfalls
- **Capture**: uses `PrintWindow` (target window only), so the overlay never captures itself — no feedback loop or flicker.
- **Coordinates / DPI**: Win32 physical pixels are converted to Qt logical pixels by `dpr` (= desktop scaling %, e.g. 1.5 for 150%). Because different emulators lay out content differently, per-target `x,y,size_x,size_y,scale_x,scale_y,content_x,content_y` overrides are provided.
- **1px drift**: round both ends of the portrait interval and take height = difference, so fractional scaling never accumulates a gap (independent of position offset).
- **Instant clear**: when the frame changes a lot, old portraits are cleared immediately (`clear_shift`), so nothing lingers during the slow scan.
- **Exclusive fullscreen** (DirectDraw/OpenGL) sits above the overlay, hiding it; prefer **windowed mode** or a **maximized (non-exclusive) window**.

## Usage
```
pip install -r requirements.txt
python san3overlay.py
```
1. Run the game in DOSBox-X / PCem (recommended: `aspect=true`, and hide the emulator menu bar).
2. Bring the emulator to the foreground — the overlay auto-replaces recognised unique-face portraits.
3. Quit: `Ctrl+Alt+Q` (global), or `Ctrl+C` in the terminal.
4. See `config.ini` for all options.

## Known limitations
- v1 upgrades unique faces 0–306 only; generic faces (>307) are left untouched.
- Automatic content-region detection is limited across window sizes/layouts; for maximized/fullscreen, manually tune `scale/content/offset` in `config.ini`.
- The overlay cannot show over exclusive fullscreen; use windowed mode.
