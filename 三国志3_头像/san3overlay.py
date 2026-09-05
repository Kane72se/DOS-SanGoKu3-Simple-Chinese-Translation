# -*- coding: utf-8 -*-
"""
Sangokushi 3 (DOS / DOSBox-X) portrait overlay prototype.

Captures the DOSBox-X window, recognises which of the 307 dedicated officer
faces is on screen (template match against assets/refs), and paints the
corresponding higher-colour face from assets/win at the same screen rect.
"""
import ctypes, os, sys, time, glob, configparser, csv, signal
from ctypes import wintypes

import cv2
import numpy as np
from PIL import Image, ImageGrab

from PySide6.QtCore import Qt, QTimer, QRect, Signal, QThread, QObject
from PySide6.QtGui import QPixmap, QPainter, QImage, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CFG = os.path.join(HERE, "config.ini")

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

user32 = ctypes.windll.user32
gdi32  = ctypes.windll.gdi32

def find_window(part):
    """Return an HWND whose title contains `part` (case-insensitive)."""
    part = part.lower()
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        ln = user32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(h, buf, ln + 1)
        if part in buf.value.lower():
            found.append(h)
            return False
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else 0

def window_title(hwnd):
    ln = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(ln + 1)
    user32.GetWindowTextW(hwnd, buf, ln + 1)
    return buf.value

def dpi_for_window(hwnd):
    """devicePixelRatio of the window's monitor (physical px per logical px)."""
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        return dpi / 96.0 if dpi else None
    except Exception:
        return None

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_uint32)]

def is_fullscreen(hwnd):
    """True if the window covers ~a monitor or its work area."""
    try:
        wr = RECT(); user32.GetWindowRect(hwnd, ctypes.byref(wr))
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        hmon = user32.MonitorFromWindow(hwnd, 2)          # MONITOR_DEFAULTTONEAREST
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        mw = mi.rcMonitor.right - mi.rcMonitor.left
        mh = mi.rcMonitor.bottom - mi.rcMonitor.top
        ww = wr.right - wr.left; wh = wr.bottom - wr.top
        if ww >= mw * 0.88 and wh >= mh * 0.88:
            return True
        waw = mi.rcWork.right - mi.rcWork.left
        wah = mi.rcWork.bottom - mi.rcWork.top
        return (ww >= waw * 0.95 and wh >= wah * 0.95)
    except Exception:
        return False

def find_fullscreen_target(target_titles, exclude=0):
    found = [0]
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        if h == exclude:
            return True
        t = window_title(h).lower()
        if any(x in t for x in target_titles) and is_fullscreen(h):
            found[0] = h
            return False
        return True
    user32.EnumWindows(cb, 0)
    return found[0]

def set_winpos(hwnd, x, y, w, h):
    """Move/resize a window in PHYSICAL screen pixels (topmost, no activate)."""
    user32.SetWindowPos(hwnd, -1, x, y, w, h, 0x0010 | 0x0040)  # NOACTIVATE|SHOWWINDOW

def foreground_target(target_titles, exclude=0):
    """Return the foreground HWND if its title matches any target substring."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd or hwnd == exclude:
        return 0
    title = window_title(hwnd).lower()
    for t in target_titles:
        if t and t in title:
            return hwnd
    return 0

def client_metrics(hwnd):
    r = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    cw, ch = r.right - r.left, r.bottom - r.top
    if cw <= 0 or ch <= 0:
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return {"x": pt.x, "y": pt.y, "w": cw, "h": ch}

def capture_printwindow(hwnd, cw, ch):
    """Capture the window's own content via PrintWindow (avoids capturing the overlay)."""
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc  = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp     = gdi32.CreateCompatibleBitmap(hwnd_dc, cw, ch)
    gdi32.SelectObject(mem_dc, bmp)
    try:
        PW_RENDERFULLCONTENT = 0x00000002
        user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
        class BIH(ctypes.Structure):
            _fields_ = [("size", ctypes.c_uint32), ("width", ctypes.c_int32),
                        ("height", ctypes.c_int32), ("planes", ctypes.c_uint16),
                        ("bitcount", ctypes.c_uint16), ("compression", ctypes.c_uint32),
                        ("sizeimage", ctypes.c_uint32), ("xppm", ctypes.c_int32),
                        ("yppm", ctypes.c_int32), ("clrused", ctypes.c_uint32),
                        ("clrimportant", ctypes.c_uint32)]
        bih = BIH(); bih.size = ctypes.sizeof(BIH); bih.width = cw
        bih.height = -ch; bih.planes = 1; bih.bitcount = 32
        buf = (ctypes.c_ubyte * (cw * ch * 4))()
        gdi32.GetDIBits(mem_dc, bmp, 0, ch, buf, ctypes.byref(bih), 0)
        arr = np.frombuffer(buf, np.uint8).reshape(ch, cw, 4)   # BGRA
        bgr = arr[:, :, :3].copy()                               # BGR, top-down
        return bgr
    finally:
        gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)

def capture_fullscreen_rect(x, y, w, h):
    """Fallback: screen grab of a rect. Caller must hide the overlay first."""
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    return np.asarray(img.convert("RGB"))[:, :, ::-1].copy()      # BGR

def is_blank(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(g.std()) < 3.0

# ---------------- game-space normalisation ----------------
def _content_rect(bgr):
    """Locate the game content (the colourful 16:10 surface) via saturation.
    Skips the DOSBox menu bar and any pillarbox/letterbox black bars."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]; val = hsv[:, :, 2]
    mask = ((sat > 40) & (val > 45)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    n, _lab, stats, _cent = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return (0, 0, bgr.shape[1], bgr.shape[0])
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(stats[idx, cv2.CC_STAT_LEFT]), int(stats[idx, cv2.CC_STAT_TOP]),
                  int(stats[idx, cv2.CC_STAT_WIDTH]), int(stats[idx, cv2.CC_STAT_HEIGHT]))
    if w < 32 or h < 32:
        return (0, 0, bgr.shape[1], bgr.shape[0])
    return (x, y, x + w, y + h)

def to_gamespace(bgr, black_bar=0):
    """Return (gameBGR 640x400, {crop_px, scale_x, scale_y}) for the content rect."""
    ch, cw = bgr.shape[:2]
    x0, y0, x1, y1 = _content_rect(bgr)
    bw, bh = x1 - x0, y1 - y0
    # The game content is 16:10 (640x400). Snap the detected box to that aspect so
    # scale_x == scale_y (square pixels -> 4:5 face) even when the bbox is a few
    # pixels tall (e.g. PCem). Centred on the detected box, clamped to the frame.
    aspect = bw / max(1, bh)
    if abs(aspect - 1.6) < 0.20:
        new_h = max(1, round(bw / 1.6))
        yc = y0 + bh // 2
        y0 = max(0, min(ch - new_h, yc - new_h // 2))
        y1 = y0 + new_h
        bh = new_h
    body = bgr[y0:y1, x0:x1]
    scale_x = bw / 640.0
    scale_y = bh / 400.0
    game = cv2.resize(body, (640, 400), interpolation=cv2.INTER_AREA)
    return game, {"crop_px": y0, "content_x": x0, "scale_x": scale_x, "scale_y": scale_y}

def _peaks(res, thr, maxn=2, excl=(16, 20)):
    """Top `maxn` local maxima above thr (with local suppression)."""
    m = res.copy(); pts = []
    for _ in range(maxn):
        _, mx, _, loc = cv2.minMaxLoc(m)
        if mx < thr:
            break
        x, y = loc; pts.append((x, y, float(mx)))
        x0 = max(0, x - excl[0]); y0 = max(0, y - excl[1])
        x1 = min(res.shape[1], x + excl[0] + 1); y1 = min(res.shape[0], y + excl[1] + 1)
        m[y0:y1, x0:x1] = -1
    return pts

# ---------------- matching engine ----------------
class MatchEngine:
    def __init__(self, refs_dir, ds=2, topk=6, scales=(1.0, 0.75, 0.5), max_faces=8):
        self.ds = ds
        self.topk = topk
        self.scales = scales
        self.max_faces = max_faces
        self.refs = []          # (full gray, small gray)
        for p in sorted(glob.glob(os.path.join(refs_dir, "*.png"))):
            g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if g is None:
                continue
            gs = cv2.resize(g, (g.shape[1] // ds, g.shape[0] // ds),
                            interpolation=cv2.INTER_AREA)
            self.refs.append((g, gs))
        self._last_hash = None
        self._last_dets = []

    def _hash(self, game_gray):
        small = cv2.resize(game_gray, (16, 10), interpolation=cv2.INTER_AREA)
        return small.tobytes()

    def detect(self, game_bgr, threshold):
        """Find all officer faces (multi-scale). Returns list of (idx, s, gx, gy, score)."""
        game_gray = cv2.cvtColor(game_bgr, cv2.COLOR_BGR2GRAY)
        h = self._hash(game_gray)
        if h == self._last_hash:
            return self._last_dets, False          # unchanged frame
        self._last_hash = h
        fd = cv2.resize(game_gray, (game_gray.shape[1] // self.ds,
                                    game_gray.shape[0] // self.ds),
                        interpolation=cv2.INTER_AREA)
        H, W = game_gray.shape
        coarse = max(0.45, threshold - 0.25)
        cands = []
        for s in self.scales:
            tw = max(6, int(64 * s / self.ds)); th = max(6, int(80 * s / self.ds))
            if tw >= fd.shape[1] or th >= fd.shape[0]:
                continue
            for i, (full, _) in enumerate(self.refs):
                tm = cv2.resize(full, (tw, th), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(fd, tm, cv2.TM_CCOEFF_NORMED)
                for (x, y, sc) in _peaks(res, coarse, maxn=2):
                    cands.append((i, s, x * self.ds, y * self.ds))
                if len(cands) >= 40:
                    break
            if len(cands) >= 40:
                break
        dets = []
        for (i, s, gx, gy) in cands:
            tw2 = int(64 * s); th2 = int(80 * s)
            tm2 = cv2.resize(self.refs[i][0], (tw2, th2), interpolation=cv2.INTER_AREA)
            if tm2.shape[0] >= H or tm2.shape[1] >= W:
                continue
            x0 = max(0, gx - 6); y0 = max(0, gy - 6)
            x1 = min(W, gx + tw2 + 6); y1 = min(H, gy + th2 + 6)
            crop = game_gray[y0:y1, x0:x1]
            res = cv2.matchTemplate(crop, tm2, cv2.TM_CCOEFF_NORMED)
            _, mx, _, mxl = cv2.minMaxLoc(res)
            if mx >= threshold:
                dets.append((i, s, x0 + mxl[0], y0 + mxl[1], float(mx)))
        dets.sort(key=lambda d: -d[4])
        kept = []
        for d in dets:
            i, s, x, y, sc = d
            cx, cy = x + 32 * s, y + 40 * s
            dup = False
            for k in kept:
                ki, ks, kx, ky, ksc = k
                if (abs(cx - (kx + 32 * ks)) < 32 * max(s, ks) and
                        abs(cy - (ky + 40 * ks)) < 40 * max(s, ks)):
                    dup = True; break
            if not dup:
                kept.append(d)
            if len(kept) >= self.max_faces:
                break
        self._last_dets = kept
        return kept, True

# ---------------- overlay window ----------------
class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._faces = []            # list of (QPixmap, QRect)
        self._pix_cache = {}
        self.enabled = True

    def exclude_from_capture(self):
        """Make Windows ignore this window in screen captures (avoids flicker)."""
        try:
            hwnd = int(self.winId())
            return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11))
        except Exception:
            return False

    def _base(self, idx, win_dir):
        if idx not in self._pix_cache:
            path = os.path.join(win_dir, f"{idx:03d}.png")
            if os.path.exists(path):
                self._pix_cache[idx] = QPixmap(path)
        return self._pix_cache.get(idx)

    def set_faces(self, faces, win_dir, content_x, crop_px, scale_x, scale_y, dpr,
                  off_x=0, off_y=0, size_x=1.0, size_y=1.0):
        """faces: list of (idx, gx, gy, s). Anchors top-left; size_x/size_y scale the
        drawn face (default 1.0 = 64x80 game-space, i.e. 4:5)."""
        if not self.enabled or not faces:
            if self._faces:
                self._faces = []; self.update()
            return
        items = []
        for (idx, gx, gy, s) in faces:
            base = self._base(idx, win_dir)
            if base is None:
                continue
            # Round both ends of the game-space interval, then take the width/height
            # as the difference.  This keeps the overlay face tiling the DOS face
            # exactly even when scale_x/scale_y are fractional (window resize), so
            # no 1px gap/overlap accumulates at the bottom.
            gw = 64 * s * size_x
            gh = 80 * s * size_y
            x0 = round((content_x + gx * scale_x + off_x) / dpr)
            y0 = round((crop_px + gy * scale_y + off_y) / dpr)
            x1 = round((content_x + (gx + gw) * scale_x + off_x) / dpr)
            y1 = round((crop_px + (gy + gh) * scale_y + off_y) / dpr)
            w = max(1, x1 - x0); h = max(1, y1 - y0)
            items.append((base.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation),
                          QRect(x0, y0, w, h)))
        self._faces = items
        self.update()

    def paintEvent(self, ev):
        if self._faces:
            p = QPainter(self)
            for pm, rect in self._faces:
                p.drawPixmap(rect, pm)

# ---------------- controller ----------------
class App(QObject):
    def __init__(self, cfg, assets):
        super().__init__()
        self.cfg = cfg; self.assets = assets
        self.name_by_face = self._load_names(os.path.join(assets["assets"], "persons_s1.csv"))
        self.engine = MatchEngine(assets["refs"], ds=cfg["ds"], topk=cfg["topk"],
                                  scales=cfg["scales"])
        self.overlay = Overlay()
        scr = QGuiApplication.primaryScreen()
        self.dpr = cfg.get("dpr", 0.0) or (scr.devicePixelRatio() if scr else 1.0)
        self._screen_mode = "auto"          # stick to fallback once proven
        self.last_metrics = None
        self._had_window = None
        self._had_faces = False
        self._target_active = None
        self._target_title = None
        self._target_dpr = 1.0
        self._last_key = None
        self._last_geom = None
        self._no_hide_capture = False
        self._pw_blank = 0
        self._no_face_frames = 0
        self._last_sig = None
        self.timer = QTimer(); self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / cfg["fps"]))
        self.quit_timer = QTimer()
        self.quit_timer.timeout.connect(self._check_quit_hotkey)
        self.quit_timer.start(60)

    def _check_quit_hotkey(self):
        u = ctypes.windll.user32
        if ((u.GetAsyncKeyState(0x51) & 0x8000) and   # Q
                (u.GetAsyncKeyState(0x11) & 0x8000) and  # Ctrl
                (u.GetAsyncKeyState(0x12) & 0x8000)):    # Alt
            print("[overlay] Ctrl+Alt+Q -> quitting.")
            QApplication.quit()

    @staticmethod
    def _load_names(path):
        m = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    v = (row.get("顏") or "").strip()
                    try:
                        fi = int(v, 0)          # handles decimal and 0x/hex-ish
                    except ValueError:
                        try: fi = int(v, 16)
                        except ValueError: continue
                    if 0 <= fi < 307:
                        m[fi] = row.get("姓名") or ""
        return m

    def relay_dets(self, dets, met):
        th = self.cfg["match_threshold"]
        faces = [(idx, gx, gy, s) for (idx, s, gx, gy, sc) in dets if sc >= th]
        key = tuple(sorted((i, round(s, 2), round(gx), round(gy))
                           for (i, gx, gy, s) in faces))
        if key != self._last_key:
            names = ", ".join("%s(%d)" % (self.name_by_face.get(i, "?"), i)
                              for (i, gx, gy, s) in faces)
            print("[overlay] faces -> %s" % (names if names else "<none>"))
            if faces:
                i0, gx0, gy0, s0 = faces[0]
                print("[overlay]   first draw: game(%d,%d) s=%.2f  scale=(%.3f,%.3f) "
                      "content=(%d,%d) client=(%d,%d)" % (
                          gx0, gy0, s0, met["scale_x"], met["scale_y"],
                          met["content_x"], met["crop_px"], met["x"], met["y"]))
            self._last_key = key
        if not faces:
            # keep current overlay for a few frames to avoid single-frame dropouts
            self._no_face_frames += 1
            if self._no_face_frames < 1:
                return
            if self._had_faces:
                self._had_faces = False
            self.overlay.set_faces([], self.assets["win"], 0, 0, 1, 1, self._target_dpr)
            return
        self._no_face_frames = 0
        self._had_faces = True
        x, y, w, h = met["x"], met["y"], met["w"], met["h"]
        # Qt setGeometry works in LOGICAL pixels -> convert the Win32 PHYSICAL
        # client rect by the known devicePixelRatio.
        geom = (int(round(x / self.dpr)), int(round(y / self.dpr)),
                int(round(w / self.dpr)), int(round(h / self.dpr)))
        if geom != self._last_geom:
            self.overlay.setGeometry(*geom)
            self._last_geom = geom
            print("[overlay]   overlay geom(logical)=%s" % (geom,))
        tun = self.cfg["target_tune"].get(
            self._target_title, (self.cfg["offset_x"], self.cfg["offset_y"], 1.0, 1.0, 0.0, 0.0, -1.0, -1.0))
        tx, ty, sxr, syr, scx, scy, ccx, ccy = tun
        if scx > 0:
            met = {**met, "scale_x": scx}
        if scy > 0:
            met = {**met, "scale_y": scy}
        if ccx >= 0:
            met = {**met, "content_x": ccx}
        if ccy >= 0:
            met = {**met, "crop_px": ccy}
        self.overlay.set_faces(faces, self.assets["win"], met["content_x"], met["crop_px"],
                               met["scale_x"], met["scale_y"], self.dpr, tx, ty, sxr, syr)

    def tick(self):
        # Only attach while the matching emulator is in the foreground.
        ov_hwnd = int(self.overlay.winId())
        hwnd = foreground_target(self.cfg["target_titles"], exclude=ov_hwnd)
        if not hwnd:
            hwnd = find_fullscreen_target(self.cfg["target_titles"], exclude=ov_hwnd)
        active = bool(hwnd)
        # store the MATCHED title substring (e.g. "pcem") as the [offsets] key
        ttl = window_title(hwnd).lower() if hwnd else ""
        self._target_title = None
        for k in self.cfg["target_tune"]:
            if k and k in ttl:
                self._target_title = k; break
        if self._target_title is None:
            for t in self.cfg["target_titles"]:
                if t and t in ttl:
                    self._target_title = t; break
        self._target_dpr = (dpi_for_window(hwnd) or self.dpr) if hwnd else self.dpr
        if active and self._target_active is not True:
            print("[overlay] target foreground -> showing.")
        if not active and self._target_active is not False:
            fg = user32.GetForegroundWindow()
            print("[overlay] target not foreground -> hidden. fg_title=%r fullscreen_hwnd=%d"
                  % (window_title(fg) if fg else "?", hwnd))
        self._target_active = active
        self.overlay.setVisible(active)
        if not active:
            self._last_key = None
            self.overlay.set_faces([], self.assets["win"], 0, 0, 1, 1, self.dpr)
            return
        if self._had_window is not True:
            print("[overlay] found %s window, starting." % self.cfg["window_title"])
            self._had_window = True
        met = client_metrics(hwnd)
        if not met:
            return
        # PrintWindow captures ONLY the DOSBox window's own content -> the
        # overlay never appears in it (no feedback loop, no flicker).
        bgr = capture_printwindow(hwnd, met["w"], met["h"])
        if bgr is None or is_blank(bgr):
            self._pw_blank += 1
            if self._pw_blank < 3:
                return                    # transient blank: keep current overlay
            # persistently blank -> fall back (overlay excluded from capture if possible)
            if self._no_hide_capture:
                bgr = capture_fullscreen_rect(met["x"], met["y"], met["w"], met["h"])
            else:
                self.overlay.hide(); QApplication.processEvents(); time.sleep(0.02)
                bgr = capture_fullscreen_rect(met["x"], met["y"], met["w"], met["h"])
                self.overlay.show()
                print("[overlay] PrintWindow blank, used full-screen fallback.")
            self._pw_blank = 0
        else:
            self._pw_blank = 0
        game, gmap = to_gamespace(bgr, self.cfg["black_bar"])
        # Clear the old faces the moment the frame changes a lot (switch to a screen
        # without a portrait), so they don't linger for the ~0.7s detect scan.
        sig = cv2.resize(cv2.cvtColor(game, cv2.COLOR_BGR2GRAY), (16, 10),
                         interpolation=cv2.INTER_AREA).astype(np.float32)
        if self._last_sig is not None and self._had_faces:
            shift = float(np.abs(sig - self._last_sig).mean())
            if shift > self.cfg.get("clear_shift", 6.0):
                self._last_key = None
                self._had_faces = False
                self.overlay.set_faces([], self.assets["win"], 0, 0, 1, 1, self.dpr)
        self._last_sig = sig
        dets, changed = self.engine.detect(game, self.cfg["match_threshold"])
        met = {**met, "content_x": gmap.get("content_x", 0),
               "crop_px": gmap["crop_px"],
               "scale_x": gmap["scale_x"], "scale_y": gmap["scale_y"]}
        self.relay_dets(dets, met)


def load_config(path):
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    def g(s, k, d):
        try: return cp.get(s, k)
        except Exception: return d
    raw_titles = g("DOSBox", "window_title", "DOSBox-X")
    target_titles = [t.strip().lower() for t in raw_titles.split(",") if t.strip()]
    # [offsets] values are "x, y" or "x, y, size_x, size_y" (per target title).
    target_tune = {}
    if cp.has_section("offsets"):
        for k, v in cp.items("offsets"):
            try:
                parts = [float(p.strip()) for p in v.split(",") if p.strip()]
            except Exception:
                continue
            if len(parts) >= 8:
                target_tune[k.strip().lower()] = (parts[0], parts[1], parts[2], parts[3],
                                                  parts[4], parts[5], parts[6], parts[7])
            elif len(parts) >= 6:
                target_tune[k.strip().lower()] = (parts[0], parts[1], parts[2], parts[3],
                                                  parts[4], parts[5], -1.0, -1.0)
            elif len(parts) >= 4:
                target_tune[k.strip().lower()] = (parts[0], parts[1], parts[2], parts[3],
                                                  0.0, 0.0, -1.0, -1.0)
            elif len(parts) == 2:
                target_tune[k.strip().lower()] = (parts[0], parts[1], 1.0, 1.0, 0.0, 0.0,
                                                  -1.0, -1.0)
    return {
        "window_title": g("DOSBox", "window_title", "DOSBox-X"),
        "target_titles": target_titles,
        "target_tune": target_tune,
        "match_threshold": float(g("Common", "match_threshold", "0.78")),
        "fps": float(g("Common", "fps", "5")),
        "black_bar": int(g("Common", "black_bar", "40")),
        "ds": int(g("Match", "ds", "2")),
        "topk": int(g("Match", "topk", "6")),
        "scales": tuple(float(x) for x in g("Match", "scales", "1.0,0.75,0.5").split(",") if x.strip()),
        "dpr": float(g("Common", "dpr", "0")),
        "hysteresis": float(g("Common", "hysteresis", "0.10")),
        "clear_shift": float(g("Common", "clear_shift", "6.0")),
        "offset_x": float(g("Common", "offset_x", "0")),
        "offset_y": float(g("Common", "offset_y", "0")),
    }

def self_test(assets):
    eng = MatchEngine(assets["refs"], ds=2, topk=6)
    frame = np.full((400, 640, 3), 60, np.uint8)
    for idx, (gx, gy) in [(2, (100, 160)), (63, (300, 60))]:
        r = cv2.imread(os.path.join(assets["refs"], f"{idx:03d}.png"))
        frame[gy:gy+80, gx:gx+64] = r
    # one small face (#102 rendered at 0.5x)
    rs = cv2.resize(cv2.imread(os.path.join(assets["refs"], "102.png")),
                    (32, 40), interpolation=cv2.INTER_AREA)
    frame[250:290, 480:512] = rs
    dets, _ = eng.detect(frame, 0.78)
    found = {(d[0], d[1]) for d in dets}
    ok = (2, 1.0) in found and (63, 1.0) in found and (102, 0.5) in found
    bad = any(d[0] == 96 and d[2] >= 360 and d[2] <= 420 for d in dets)
    ok = ok and not bad
    for d in dets:
        print("[selftest] det idx=%d s=%.2f at(%d,%d) score=%.2f" % (d[0], d[1], d[2], d[3], d[4]))
    print("[selftest] multi-face " + ("PASS" if ok else "FAIL"))
    return ok


def main():
    # Qt sets PER_MONITOR_AWARE_V2 DPI awareness by default; do NOT call the
    # Win32 DPI setter ourselves (it fails once Qt has set the context).
    try:
        signal.signal(signal.SIGINT, signal.SIG_DFL)   # make Ctrl+C in console quit
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cfg_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".ini") else DEFAULT_CFG
    assets = {
        "refs": os.path.join(HERE, "assets", "refs"),
        "win":  os.path.join(HERE, "assets", "win"),
        "assets": os.path.join(HERE, "assets"),
    }
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        self_test(assets); return
    cfg = load_config(cfg_path)
    QApp = QApplication(sys.argv)
    app = App(cfg, assets)
    app.overlay.show()
    # NOTE: intentionally do NOT call SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)
    # on the overlay, so that normal screen captures (Win+Shift+S / PrintScreen) DO
    # include the hi-res portrait layer.  The overlay's own capture uses PrintWindow
    # (captures the emulator window only, not the overlay), so this is safe.
    sys.exit(QApp.exec())

if __name__ == "__main__":
    main()
