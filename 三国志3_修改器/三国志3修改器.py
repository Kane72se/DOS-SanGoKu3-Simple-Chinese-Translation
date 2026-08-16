# -*- coding: utf-8 -*-
"""三国志3（DOS 繁体版）存档/剧本修改器（全字段版）

用法: pythonw 三国志3修改器.py
同目录需放 full_table.bin 与 han_map_v20.tsv（用于显示武将名字）。

支持文件:
  - SANGOKU3.SAV     游戏存档（自动定位武将数据块）
  - SNDATA1B~6B.CIM  六个剧本的武将数据

每名武将 49 字节。字段依据:
  PTT yuxio《三國志3代修改》DOS 版结构说明 + 本项目对 SNDATA/SANGOKU 的逆向验证。
  标“推测”的字段为分析推断，未在游戏中逐项验证。
"""

import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from zhconv import convert as _zh_convert
except Exception:
    _zh_convert = None

REC_SIZE = 49
N_OFFICERS = 600
BLOCK_BYTES = REC_SIZE * N_OFFICERS

# 能力六维（偏移固定）
ABIL = [('lu', 17, '陆指'), ('shui', 18, '水指'), ('wu', 19, '武力'),
        ('zhi', 20, '智力'), ('zheng', 21, '政治'), ('mei', 22, '魅力')]

# 其余字段规格: (key, 标签, 偏移, 长度, 最小值, 最大值, 类型, 提示)
# 类型: int / nib_hi / nib_lo / disease / spy / lifespan / birth
EXTRA_SPECS = [
    ('portrait', '头像', 2, 2, 0, 65535, 'int', '0-65535；>307 为大众脸合成'),
    ('next', '次席(链表)', 4, 2, 0, 65535, 'int', '进阶：下一位武将链接，0xFFFF=末尾，乱改会断链表'),
    ('amb', '野心', 10, 1, 0, 15, 'nib_hi', '0-15（推测）'),
    ('calm', '冷静', 10, 1, 0, 15, 'nib_lo', '0-15（推测）'),
    ('brave', '勇猛', 11, 1, 0, 15, 'nib_hi', '0-15（推测）'),
    ('luck', '运气', 11, 1, 0, 15, 'nib_lo', '0-15（推测）'),
    ('acted', '行动', 12, 1, 0, 1, 'int', '0=未行动 1=已行动'),
    ('disease', '疾病(月数)', 13, 1, 0, 7, 'disease', '0=无病 1-7=患病剩余月数'),
    ('life', '寿命', 14, 1, 0, 15, 'lifespan', '0-15，存于高4位'),
    ('spy', '埋伏', 15, 1, 0, 1, 'spy', '0=正常 1=埋伏中(写入8)'),
    ('status', '身份', 16, 1, 0, 255, 'int', '0=君主(确定)，1-6 为军师/将军/武官/文官/在野/放浪（推测）'),
    ('xiang', '相性', 23, 1, 0, 150, 'int', '1-150；如曹操25 刘备75 袁绍101'),
    ('yi', '义理', 24, 1, 0, 100, 'int', '0-100；如刘备/关羽100'),
    ('loy', '忠诚', 25, 1, 0, 100, 'int', '0-100；君主通常为0'),
    ('city', '所在城市', 26, 1, 0, 255, 'int', '城市编号 0-45（推测）'),
    ('lord', '所属势力', 27, 1, 0, 255, 'int', '势力编号，255(FF)=无/在野（推测）'),
    ('rank', '仕官', 28, 1, 0, 255, 'int', '仕官状态（推测）'),
    ('hcity', '里所在', 29, 1, 0, 255, 'int', '埋伏时原所在（推测）'),
    ('hlord', '里所属', 30, 1, 0, 255, 'int', '埋伏时原所属（推测）'),
    ('family', '亲族', 31, 1, 0, 255, 'int', '家族编号，255(FF)=无（推测）'),
    ('train', '训练', 32, 1, 0, 100, 'int', '部队训练度（推测）'),
    ('mora', '士气', 33, 1, 0, 100, 'int', '部队士气（推测）'),
    ('birth', '出生年', 37, 1, 0, 255, 'birth', '推测：公元年份，如曹操155'),
    ('work', '工作', 38, 1, 0, 255, 'int', '255(FF)=无 2=搜索（推测）'),
    ('workm', '工作剩余月', 39, 1, 0, 255, 'int', '工作剩余月数（推测）'),
]

# 静态能力字段：改存档时同步写入对应剧本文件（游戏读档显示武将情报时可能读剧本）
SYNC_SPECS = [
    ('portrait', '头像', 2, 2, 0, 65535, 'int', ''),
    ('life', '寿命', 14, 1, 0, 15, 'lifespan', ''),
    ('lu', '陆指', 17, 1, 1, 100, 'int', ''),
    ('shui', '水指', 18, 1, 1, 100, 'int', ''),
    ('wu', '武力', 19, 1, 1, 100, 'int', ''),
    ('zhi', '智力', 20, 1, 1, 100, 'int', ''),
    ('zheng', '政治', 21, 1, 1, 100, 'int', ''),
    ('mei', '魅力', 22, 1, 1, 100, 'int', ''),
    ('xiang', '相性', 23, 1, 0, 150, 'int', ''),
    ('yi', '义理', 24, 1, 0, 100, 'int', ''),
    ('birth', '出生年', 37, 1, 0, 255, 'birth', ''),
]

# 城市字段：记录 = [70字节数据][4字节名字]，字段偏移相对记录起点（名字-0x46）
# 含义已用剧本1陈留的初始数值核对（人口存值=显示值/100）
CITY_FIELDS = [
    ('cpop', '人口', 0x1D, 2, 0, 3000000, 'pop100'),
    ('cgold', '金', 0x1F, 2, 0, 50000, 'int'),
    ('cric', '军粮', 0x21, 3, 0, 3000000, 'int'),
    ('cdev', '开发', 0x2F, 1, 0, 100, 'int'),
    ('cfarm', '耕作', 0x30, 1, 0, 100, 'int'),
    ('cirr', '灌溉', 0x31, 1, 0, 100, 'int'),
    ('cwater', '治水', 0x32, 1, 0, 100, 'int'),
    ('ctrade', '商业', 0x33, 2, 0, 9999, 'int'),
    ('ctax', '税率', 0x35, 1, 0, 100, 'int'),
    ('cloy', '民忠', 0x36, 1, 0, 100, 'int'),
    ('cbow', '弓', 0x37, 2, 0, 9999, 'int'),
    ('cbow2', '强弓', 0x39, 2, 0, 9999, 'int'),
    ('chorse', '军马', 0x3B, 2, 0, 9999, 'int'),
    ('cship', '战舰', 0x3D, 1, 0, 100, 'int'),
    ('cship2', '重舰', 0x3F, 1, 0, 100, 'int'),
    ('cship3', '轻舰', 0x40, 1, 0, 100, 'int'),
]


def find_data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [here,
                  os.path.join(here, '..'),
                  r'C:\Users\admin\Documents\Codex\2026-08-10\zha\work']
    for d in candidates:
        if os.path.isfile(os.path.join(d, 'full_table.bin')) and \
           os.path.isfile(os.path.join(d, 'han_map_v20.tsv')):
            return d
    return None


ITEM_COUNT = 16


def load_items():
    """从同目录 宝物列表.txt 读取 宝物id->名称；无文件时用占位名。"""
    items = {}
    d = find_data_dir()
    if d:
        p = os.path.join(d, '宝物列表.txt')
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    s = line.rstrip('\r\n')
                    if not s.strip() or s.lstrip().startswith('#'):
                        continue
                    parts = s.split('\t')
                    if len(parts) >= 2:
                        try:
                            items[int(parts[0])] = parts[1].strip()
                        except ValueError:
                            pass
    for i in range(ITEM_COUNT):
        items.setdefault(i, '宝物%d' % i)
    return [items[i] for i in range(ITEM_COUNT)]


class NameTable:
    def __init__(self):
        d = find_data_dir()
        if d is None:
            raise RuntimeError('找不到 full_table.bin / han_map_v20.tsv，请把它们放在程序同目录')
        raw = open(os.path.join(d, 'full_table.bin'), 'rb').read()
        self.code2slot = {}
        for s in range(len(raw) // 2):
            v = raw[s*2] | (raw[s*2+1] << 8)
            self.code2slot.setdefault(v, s)
        self.slot2char = {}
        with open(os.path.join(d, 'han_map_v20.tsv'), encoding='utf-8') as f:
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) >= 2:
                    try:
                        self.slot2char[int(p[0])] = p[1]
                    except ValueError:
                        pass

    def name(self, rec):
        out = []
        for i in range(43, 49, 2):
            v = (rec[i] << 8) | rec[i+1]
            if v == 0:
                break
            s = self.code2slot.get(v)
            out.append(self.slot2char.get(s, '?') if s is not None else '?')
        return ''.join(out)


class EditorCore:
    """与界面无关的读写逻辑，便于测试。"""

    def __init__(self, names):
        self.names = names
        self.path = None
        self.raw = None
        self.base = None
        self.cities_only = False

    def _valid(self, off):
        if off + REC_SIZE > len(self.raw):
            return False
        rec = self.raw[off:off+REC_SIZE]
        if any(b > 100 for b in rec[17:23]):
            return False
        nm = self.names.name(rec)
        return 1 <= len(nm) <= 3 and '?' not in nm

    def detect_base(self, fname):
        name = os.path.basename(fname).upper()
        if name.startswith('SNDATA') and name.endswith('.CIM'):
            if len(self.raw) >= BLOCK_BYTES and self._valid(0) and self._valid(REC_SIZE):
                return 0
        best = None
        best_cnt = 0
        limit = len(self.raw) - BLOCK_BYTES
        for off in range(0, limit + 1):
            if not (self._valid(off) and self._valid(off+REC_SIZE) and
                    self._valid(off+2*REC_SIZE) and self._valid(off+3*REC_SIZE)):
                continue
            cnt = 4
            o = off + 4*REC_SIZE
            while o + REC_SIZE <= len(self.raw) and self._valid(o):
                cnt += 1
                o += REC_SIZE
            if cnt > best_cnt:
                best_cnt = cnt
                best = off
        if best is None or best_cnt < 100:
            raise RuntimeError('未能在文件中定位武将数据块')
        return best

    def open(self, path):
        self.path = path
        self.raw = bytearray(open(path, 'rb').read())
        try:
            self.base = self.detect_base(path)
        except RuntimeError:
            self.base = None
        self.cities_only = self.base is None
        if self.base is None:
            return
        if self.base + BLOCK_BYTES > len(self.raw):
            raise RuntimeError('文件过短，无法容纳 600 名武将')

    def rec(self, idx):
        off = self.base + idx*REC_SIZE
        return self.raw[off:off+REC_SIZE]

    def save(self, path=None):
        target = path or self.path
        if os.path.exists(target):
            shutil.copyfile(target, target + '.bak')
        with open(target, 'wb') as f:
            f.write(self.raw)
        return target

    # ---- 字段读写 ----
    def get_int(self, idx, off, size=1):
        o = self.base + idx*REC_SIZE + off
        return int.from_bytes(self.raw[o:o+size], 'little')

    def set_int(self, idx, off, value, size=1):
        o = self.base + idx*REC_SIZE + off
        self.raw[o:o+size] = value.to_bytes(size, 'little')

    def get_nib(self, idx, off, hi):
        b = self.raw[self.base + idx*REC_SIZE + off]
        return (b >> 4) if hi else (b & 0xF)

    def set_nib(self, idx, off, value, hi):
        o = self.base + idx*REC_SIZE + off
        b = self.raw[o]
        if hi:
            b = (b & 0x0F) | ((value & 0xF) << 4)
        else:
            b = (b & 0xF0) | (value & 0xF)
        self.raw[o] = b

    def get_disease(self, idx):
        b = self.raw[self.base + idx*REC_SIZE + 13] & 0x0F
        return b & 0x07

    def set_disease(self, idx, value):
        o = self.base + idx*REC_SIZE + 13
        low = (0x08 if value > 0 else 0) | (value & 0x07)
        self.raw[o] = (self.raw[o] & 0xF0) | low

    def get_spy(self, idx):
        return 1 if self.raw[self.base + idx*REC_SIZE + 15] == 8 else 0

    def set_spy(self, idx, value):
        self.raw[self.base + idx*REC_SIZE + 15] = 8 if value else 0

    def get_life(self, idx):
        return self.raw[self.base + idx*REC_SIZE + 14] >> 4

    def set_life(self, idx, value):
        o = self.base + idx*REC_SIZE + 14
        self.raw[o] = (self.raw[o] & 0x0F) | ((value & 0xF) << 4)

    def read_field(self, idx, spec):
        key, label, off, size, lo, hi, kind, note = spec
        if kind == 'nib_hi':
            return self.get_nib(idx, off, True)
        if kind == 'nib_lo':
            return self.get_nib(idx, off, False)
        if kind == 'disease':
            return self.get_disease(idx)
        if kind == 'spy':
            return self.get_spy(idx)
        if kind == 'lifespan':
            return self.get_life(idx)
        return self.get_int(idx, off, size)

    def write_field(self, idx, spec, value):
        key, label, off, size, lo, hi, kind, note = spec
        if kind == 'nib_hi':
            self.set_nib(idx, off, value, True)
        elif kind == 'nib_lo':
            self.set_nib(idx, off, value, False)
        elif kind == 'disease':
            self.set_disease(idx, value)
        elif kind == 'spy':
            self.set_spy(idx, value)
        elif kind == 'lifespan':
            self.set_life(idx, value)
        else:
            self.set_int(idx, off, value, size)


class App:
    def __init__(self, root):
        self.root = root
        self.names = NameTable()
        self.core = EditorCore(self.names)
        self.cur_idx = None
        self.vars = {}
        self.items = load_items()
        self.item_rows = []
        self.scn_core = None
        self.scn_name = ''
        self.scn_dirty = False
        self.sync_var = tk.BooleanVar(value=False)
        self.cities = []
        self.cur_city = None
        self.city_vars = {}
        self.battle_offs = set()
        self._build()

    def _build(self):
        root = self.root
        root.title('三国志3（DOS）修改器 — 全字段版')
        root.geometry('1080x760')

        top = ttk.Frame(root, padding=6)
        top.pack(fill='x')
        ttk.Button(top, text='打开存档 SANGOKU3.SAV', command=self.open_save).pack(side='left')
        ttk.Button(top, text='打开剧本 SNDATA*.CIM', command=self.open_scenario).pack(side='left', padx=(6, 0))
        ttk.Button(top, text='打开城市剧本', command=self.open_city_scenario).pack(side='left', padx=(6, 0))
        ttk.Button(top, text='保存', command=self.save_file).pack(side='left', padx=(6, 0))
        ttk.Label(top, text='查找:').pack(side='left', padx=(18, 4))
        self.search = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.search, width=14)
        ent.pack(side='left')
        ent.bind('<KeyRelease>', lambda ev: self.refresh())
        self.status = tk.StringVar(value='未打开文件')
        ttk.Label(root, textvariable=self.status, relief='sunken', anchor='w', padding=4).pack(fill='x')

        mid = ttk.Frame(root, padding=6)
        mid.pack(fill='both', expand=True)
        cols = ('no', 'name', 'troop', 'loy', 'xiang', 'yi',
                'lu', 'shui', 'wu', 'zhi', 'zheng', 'mei')
        headers = ('编号', '名字', '兵力', '忠诚', '相性', '义理',
                   '陆', '水', '武', '智', '政', '魅')
        widths = (50, 110, 64, 50, 50, 50, 42, 42, 42, 42, 42, 42)
        self.tree = ttk.Treeview(mid, columns=cols, show='headings', height=16)
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor='center')
        vsb = ttk.Scrollbar(mid, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.on_select)

        edit = ttk.LabelFrame(root, text='编辑所选武将（名字只读）', padding=8)
        edit.pack(fill='both', padx=6, pady=(0, 6))
        self.cur_name = tk.StringVar(value='')
        ttk.Label(edit, textvariable=self.cur_name,
                  font=('Microsoft YaHei', 12, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w')

        nb = ttk.Notebook(edit)
        nb.grid(row=1, column=0, columnspan=3, sticky='we', pady=(4, 0))
        self.tab_base = ttk.Frame(nb, padding=6)
        self.tab_abil = ttk.Frame(nb, padding=6)
        self.tab_hide = ttk.Frame(nb, padding=6)
        self.tab_city = ttk.Frame(nb, padding=6)
        nb.add(self.tab_base, text='基础')
        nb.add(self.tab_abil, text='能力')
        nb.add(self.tab_hide, text='隐藏/其他')
        nb.add(self.tab_city, text='城市')

        base_specs = [s for s in EXTRA_SPECS if s[0] in
                      ('portrait', 'next', 'birth')]
        abil_specs = [('troop', '兵力', 6, 2, 0, 65535, 'int', '0-65535')] + \
                     [(k, lab, off, 1, 1, 100, 'int', '1-100') for k, off, lab in ABIL] + \
                     [s for s in EXTRA_SPECS if s[0] in ('xiang', 'yi', 'loy')]
        hide_specs = [s for s in EXTRA_SPECS if s[0] in
                      ('amb', 'calm', 'brave', 'luck', 'acted', 'disease', 'life', 'spy',
                       'status', 'city', 'lord', 'rank', 'hcity', 'hlord', 'family',
                       'train', 'mora', 'work', 'workm')]

        self._fill_tab(self.tab_base, base_specs, 2)
        self._fill_tab(self.tab_abil, abil_specs, 2)
        self._fill_tab(self.tab_hide, hide_specs, 2)

        # ---- 城市页 ----
        ccols = ('cno', 'cname', 'cpop', 'cgold', 'cric', 'cdev', 'cfarm', 'cirr',
                 'cwater', 'ctrade', 'ctax', 'cloy', 'cbow', 'cbow2', 'chorse')
        cheaders = ('#', '城市', '人口', '金', '军粮', '开发', '耕作', '灌溉',
                    '治水', '商业', '税率', '民忠', '弓', '强弓', '军马')
        cwidths = (40, 90, 70, 60, 60, 45, 45, 45, 45, 60, 45, 45, 40, 40, 45)
        cframe = ttk.Frame(self.tab_city)
        cframe.pack(fill='both', expand=True)
        self.city_tree = ttk.Treeview(cframe, columns=ccols, show='headings', height=12)
        for c, h, w in zip(ccols, cheaders, cwidths):
            self.city_tree.heading(c, text=h)
            self.city_tree.column(c, width=w, anchor='center')
        cvsb = ttk.Scrollbar(cframe, orient='vertical', command=self.city_tree.yview)
        self.city_tree.configure(yscrollcommand=cvsb.set)
        self.city_tree.pack(side='left', fill='both', expand=True)
        cvsb.pack(side='right', fill='y')
        self.city_tree.bind('<<TreeviewSelect>>', self.on_city_select)

        cedit = ttk.LabelFrame(self.tab_city, text='编辑所选城市（数值已与剧本1陈留初始值核对）', padding=6)
        cedit.pack(fill='x', pady=(4, 0))
        self.cur_city_name = tk.StringVar(value='')
        ttk.Label(cedit, textvariable=self.cur_city_name, font=('Microsoft YaHei', 11, 'bold')).grid(
            row=0, column=0, columnspan=8, sticky='w')
        for i, (key, lab, off, size, lo, hi, kind) in enumerate(CITY_FIELDS):
            rr, cc = divmod(i, 8)
            ttk.Label(cedit, text=lab).grid(row=1+rr, column=cc*2, sticky='e', padx=(0, 3))
            v = tk.StringVar()
            ttk.Entry(cedit, textvariable=v, width=8).grid(row=1+rr, column=cc*2+1, sticky='w')
            self.city_vars[key] = v
        ttk.Button(cedit, text='应用到所选城市', command=self.apply_city).grid(
            row=4, column=0, columnspan=16, sticky='w', pady=(5, 0))
        ttk.Label(cedit, text='人口存值=显示值/100；改前请备份 .bak。',
                  foreground='#999').grid(row=5, column=0, columnspan=16, sticky='w', pady=(3, 0))

        itemf = ttk.LabelFrame(self.tab_base, padding=4)
        itemf.grid(row=30, column=0, columnspan=4, sticky='we', pady=(10, 0))
        ttk.Label(itemf, text='宝物（每格一件，可增删；名称取自 宝物列表.txt，可自行编辑）',
                  foreground='#555').grid(row=0, column=0, columnspan=3, sticky='w')
        self.item_frame = ttk.Frame(itemf)
        self.item_frame.grid(row=1, column=0, columnspan=3, sticky='we', pady=(4, 0))
        ttk.Label(itemf, text='添加宝物:').grid(row=2, column=0, sticky='e', pady=(6, 0))
        self.add_item_var = tk.StringVar(value='(无)')
        addcb = ttk.Combobox(itemf, textvariable=self.add_item_var, state='readonly', width=22)
        addcb.grid(row=2, column=1, sticky='w', pady=(6, 0))
        addcb['values'] = ['(无)'] + ['%d. %s' % (i, n) for i, n in self._valid_items()]
        addcb.bind('<<ComboboxSelected>>', lambda ev: self.on_add_item())

        btns = ttk.Frame(edit)
        btns.grid(row=2, column=0, columnspan=3, sticky='we', pady=(6, 0))
        ttk.Button(btns, text='应用到所选武将', command=self.apply_all).pack(side='left')
        ttk.Button(btns, text='恢复原始值', command=self.show_selected).pack(side='left', padx=(6, 0))
        ttk.Label(btns, text='批量：筛出武将兵力全部设为').pack(side='left', padx=(24, 4))
        self.batch_var = tk.StringVar()
        ttk.Entry(btns, textvariable=self.batch_var, width=8).pack(side='left')
        ttk.Button(btns, text='应用', command=self.apply_batch).pack(side='left', padx=(4, 0))
        ttk.Label(btns, text='（留空则全部600人）', foreground='#666').pack(side='left', padx=6)
        ttk.Checkbutton(btns, text='能力同步写入剧本', variable=self.sync_var).pack(side='left', padx=(12, 0))
        ttk.Label(btns, text='保存前自动备份 .bak；改存档前先退出游戏。',
                  foreground='#888').pack(side='right')

    def _fill_tab(self, tab, specs, cols):
        for i, spec in enumerate(specs):
            key, label, off, size, lo, hi, kind, note = spec
            r, c = divmod(i, cols)
            ttk.Label(tab, text=label).grid(row=r, column=c*2, sticky='e', padx=(0, 4), pady=2)
            v = tk.StringVar()
            e = ttk.Entry(tab, textvariable=v, width=9)
            e.grid(row=r, column=c*2+1, sticky='w', pady=2)
            self.vars[key] = v
            if note:
                ttk.Label(tab, text=note, foreground='#999').grid(
                    row=r, column=c*2+1, sticky='w', padx=(76, 0), pady=2)
        # 让备注不重叠：占位
        for c in range(cols):
            tab.columnconfigure(c*2+1, minsize=330)

    # ---- 宝物格子 ----
    def _valid_items(self):
        return [(i, n) for i, n in enumerate(self.items) if n]

    def _item_vals(self):
        return ['(无)'] + ['%d. %s' % (i, n) for i, n in self._valid_items()]

    def _val_for(self, iid):
        for i, n in self._valid_items():
            if i == iid:
                return '%d. %s' % (i, n)
        return None

    def _item_id(self, s):
        if not s or s == '(无)':
            return None
        try:
            return int(s.split('.')[0])
        except (ValueError, IndexError):
            return None

    def add_item_row(self, iid=None):
        row = ttk.Frame(self.item_frame)
        row.pack(fill='x', pady=1)
        var = tk.StringVar()
        vals = self._item_vals()
        if iid is not None:
            var.set(self._val_for(iid))
        cb = ttk.Combobox(row, textvariable=var, values=vals, state='readonly', width=22)
        cb.pack(side='left')
        btn = ttk.Button(row, text='移除', width=5,
                         command=lambda: self.remove_item_row(row))
        btn.pack(side='left', padx=4)
        self.item_rows.append((row, var))

    def remove_item_row(self, row):
        self.item_rows = [x for x in self.item_rows if x[0] is not row]
        row.destroy()

    def on_add_item(self):
        iid = self._item_id(self.add_item_var.get())
        if iid is None:
            return
        self.add_item_row(iid)
        self.add_item_var.set('(无)')

    def rebuild_item_rows(self, ids):
        for row, _ in self.item_rows:
            row.destroy()
        self.item_rows = []
        valid = {i for i, _ in self._valid_items()}
        for iid in ids:
            if iid in valid:
                self.add_item_row(iid)

    def collect_item_ids(self):
        ids = []
        valid = {i for i, _ in self._valid_items()}
        for _, var in self.item_rows:
            iid = self._item_id(var.get())
            if iid is not None and iid in valid:
                ids.append(iid)
        return ids

    def open_save(self):
        p = filedialog.askopenfilename(title='选择存档',
                                       filetypes=[('三国志3存档', 'SANGOKU3.SAV'), ('所有文件', '*.*')])
        if p:
            self.load(p)

    def open_scenario(self):
        p = filedialog.askopenfilename(title='选择剧本武将数据',
                                       filetypes=[('剧本武将数据',
                                                   'SNDATA1B.CIM SNDATA2B.CIM SNDATA3B.CIM '
                                                   'SNDATA4B.CIM SNDATA5B.CIM SNDATA6B.CIM'),
                                                  ('所有文件', '*.*')])
        if not p:
            return
        base = os.path.basename(p)
        if not re.match(r'^SNDATA[1-6]B\.CIM$', base, re.I):
            messagebox.showerror('文件不对',
                                 '武将剧本只能是 SNDATA1B~6B.CIM 中的一个\n'
                                 '当前选择：%s' % base)
            return
        self.load(p)

    def open_city_scenario(self):
        p = filedialog.askopenfilename(title='选择城市剧本数据',
                                       filetypes=[('城市剧本数据',
                                                   'SNDATA1.CIM SNDATA2.CIM SNDATA3.CIM '
                                                   'SNDATA4.CIM SNDATA5.CIM SNDATA6.CIM'),
                                                  ('所有文件', '*.*')])
        if not p:
            return
        base = os.path.basename(p)
        if not re.match(r'^SNDATA[1-6]\.CIM$', base, re.I):
            messagebox.showerror('文件不对',
                                 '城市剧本只能是 SNDATA1~6.CIM 中的一个\n'
                                 '当前选择：%s' % base)
            return
        self.load(p)

    def load(self, path):
        try:
            self.core.open(path)
        except Exception as ex:
            messagebox.showerror('打不开', str(ex))
            return
        self.scn_core = None
        self.scn_name = ''
        self.scn_dirty = False
        base_name = os.path.basename(path)
        if self.core.cities_only:
            self.cities = self._scan_cities()
            self.refresh_cities()
            self.status.set('%s — 城市数据，共 %d 座（武将能力不可用）' % (base_name, len(self.cities)))
            return
        msg = '%s — 武将块偏移 0x%X，共 %d 人' % (base_name, self.core.base, N_OFFICERS)
        if base_name.upper() == 'SANGOKU3.SAV':
            d = os.path.dirname(os.path.abspath(path))
            best = None
            best_name = ''
            best_score = 0
            for i in range(1, 7):
                p = os.path.join(d, 'SNDATA%dB.CIM' % i)
                if not os.path.isfile(p):
                    continue
                try:
                    c = EditorCore(self.names)
                    c.open(p)
                except Exception:
                    continue
                score = 0
                for k in range(10):
                    if self.names.name(self.core.rec(k)) == self.names.name(c.rec(k)):
                        score += 1
                    else:
                        break
                if score > best_score:
                    best_score = score
                    best = c
                    best_name = os.path.basename(p)
            if best is not None and best_score >= 1:
                self.scn_core = best
                self.scn_name = best_name
                msg += ' | 匹配剧本: %s（勾选“能力同步写入剧本”后，改能力会同时写入该文件）' % best_name
            else:
                msg += ' | 未找到同目录剧本文件，能力同步不可用'
        self.status.set(msg)
        self.refresh()
        self.cities = self._scan_cities()
        self.refresh_cities()

    # ---- 城市 ----
    def _scan_cities(self):
        raw = self.core.raw
        base_name = os.path.basename(self.core.path).upper()
        if base_name.startswith('SNDATA'):
            lo, hi = 0x100, min(len(raw), 0x1500)
        else:
            lo, hi = 0x1D0, min(len(raw), 0x5400)
        hits = []
        for off in range(lo, hi - 8):
            if raw[off+4] != 0 or raw[off+5] != 0:
                continue
            v1 = (raw[off] << 8) | raw[off+1]
            v2 = (raw[off+2] << 8) | raw[off+3]
            s1 = self.names.code2slot.get(v1)
            if s1 is None:
                continue
            if v2 == 0:
                # 1字城市名：后 4 字节为 0
                if raw[off+2] == 0 and raw[off+3] == 0 and raw[off+4] == 0 and raw[off+5] == 0:
                    ch = self.names.slot2char.get(s1, '')
                    if len(ch) == 1 and '?' not in ch:
                        hits.append((off, ch))
                continue
            s2 = self.names.code2slot.get(v2)
            if s2 is None:
                continue
            nm2 = self.names.slot2char.get(s1, '') + self.names.slot2char.get(s2, '')
            if len(nm2) != 2 or '?' in nm2:
                continue
            if nm2 in ('囊書', '要術', '天劍', '藍劍', '月刀', '的盧', '飛電', '玉輿'):
                continue
            start = off
            nm = nm2
            # 4字城市名：off-4..off-1 是两个可解码码
            if off >= 4:
                p1 = (raw[off-4] << 8) | raw[off-3]
                p2 = (raw[off-2] << 8) | raw[off-1]
                ps1 = self.names.code2slot.get(p1)
                ps2 = self.names.code2slot.get(p2)
                if ps1 is not None and ps2 is not None:
                    pre = self.names.slot2char.get(ps1, '') + self.names.slot2char.get(ps2, '')
                    if len(pre) == 2 and '?' not in pre:
                        start = off - 4
                        nm = pre + nm
            # 3字城市名：off-2..off-1 是一个可解码码
            if start == off and off >= 2:
                p = (raw[off-2] << 8) | raw[off-1]
                ps = self.names.code2slot.get(p)
                if ps is not None:
                    pre = self.names.slot2char.get(ps, '')
                    if len(pre) == 1 and '?' not in pre:
                        start = off - 2
                        nm = pre + nm
            hits.append((start, nm))
        out = []
        last = -100
        for off, nm in hits:
            if off - last < 0x3E:
                continue
            out.append((nm, off))
            last = off
        # 战场（关口）表：22 条 × 0x19 字节，名字在记录开头
        self.battle_offs = set()
        bls = raw.find(bytes.fromhex('93f49bd692d3'))  # 白狼山
        if bls >= 0:
            for i in range(22):
                bo = bls + i * 0x19
                if bo + 0x19 > len(raw):
                    break
                nm = self._decode_name(raw, bo)
                if nm:
                    out.append((nm, bo))
                    self.battle_offs.add(bo)
        seen = set()
        out2 = []
        for nm, off in out:
            if off in seen:
                continue
            seen.add(off)
            out2.append((nm, off))
        return out2

    def _decode_name(self, raw, off):
        chars = []
        for k in range(4):
            v = (raw[off+k*2] << 8) | raw[off+k*2+1]
            if v == 0:
                break
            s = self.names.code2slot.get(v)
            if s is None:
                break
            ch = self.names.slot2char.get(s, '')
            if not ch or ch == '?':
                break
            chars.append(ch)
        return ''.join(chars)

    def refresh_cities(self):
        if not hasattr(self, 'city_tree'):
            return
        self.city_tree.delete(*self.city_tree.get_children())
        for i, (nm, off) in enumerate(self.cities):
            r = self.core.raw
            if off in self.battle_offs:
                self.city_tree.insert('', 'end', iid=str(i),
                                      values=(i+1, nm + '（战场）', '—', '—', '—', '—', '—', '—',
                                              '—', '—', '—', '—', '—', '—', '—'))
                continue
            base = off - 0x46
            def gi(o, s):
                return int.from_bytes(r[base+o:base+o+s], 'little')
            self.city_tree.insert('', 'end', iid=str(i), values=(
                i+1, nm, gi(0x1D, 2)*100, gi(0x1F, 2), gi(0x21, 3),
                r[base+0x2F], r[base+0x30], r[base+0x31], r[base+0x32],
                gi(0x33, 2), r[base+0x35], r[base+0x36], gi(0x37, 2),
                gi(0x39, 2), gi(0x3B, 2)))

    def on_city_select(self, _ev=None):
        sel = self.city_tree.selection()
        if not sel:
            return
        self.cur_city = int(sel[0])
        self.show_city()

    def show_city(self):
        if self.cur_city is None or self.cur_city >= len(self.cities):
            return
        nm, off = self.cities[self.cur_city]
        if off in self.battle_offs:
            self.cur_city_name.set('%d. %s（战场/关口：无城市数值，只读）' % (self.cur_city + 1, nm))
            for key in self.city_vars:
                self.city_vars[key].set('')
            return
        self.cur_city_name.set('%d. %s' % (self.cur_city + 1, nm))
        r = self.core.raw
        base = off - 0x46
        for key, lab, o, size, lo, hi, kind in CITY_FIELDS:
            v = int.from_bytes(r[base+o:base+o+size], 'little')
            if kind == 'pop100':
                v = v * 100
            self.city_vars[key].set(str(v))

    def apply_city(self):
        if self.cur_city is None or self.cur_city >= len(self.cities):
            messagebox.showinfo('提示', '先在列表里选一座城市')
            return
        nm, off = self.cities[self.cur_city]
        if off in self.battle_offs:
            messagebox.showinfo('提示', '%s 是战场（关口），没有城市数值可改' % nm)
            return
        base = off - 0x46
        try:
            for key, lab, o, size, lo, hi, kind in CITY_FIELDS:
                s = self.city_vars[key].get().strip()
                try:
                    v = int(s)
                except ValueError:
                    raise ValueError('%s 必须填数字' % lab)
                if not (lo <= v <= hi):
                    raise ValueError('%s 超出范围 %d~%d' % (lab, lo, hi))
                if kind == 'pop100':
                    v = v // 100
                self.core.raw[base+o:base+o+size] = v.to_bytes(size, 'little')
        except ValueError as ex:
            messagebox.showerror('输入有误', str(ex))
            return
        self.status.set('已修改城市 %s（未保存）' % nm)
        self.refresh_cities()
        self.city_tree.selection_set(str(self.cur_city))

    def filtered_idx(self):
        q = self.search.get().strip()
        if not q:
            for i in range(N_OFFICERS):
                yield i, self.names.name(self.core.rec(i))
            return
        variants = {q}
        if _zh_convert:
            try:
                variants.add(_zh_convert(q, 'zh-cn'))
                variants.add(_zh_convert(q, 'zh-hant'))
            except Exception:
                pass
        variants = {v for v in variants if v}
        for i in range(N_OFFICERS):
            nm = self.names.name(self.core.rec(i))
            if q.isdigit() and int(q) == i + 1:
                yield i, nm
            elif any(v in nm for v in variants):
                yield i, nm

    def refresh(self):
        if self.core.base is None:
            return
        self.tree.delete(*self.tree.get_children())
        for i, nm in self.filtered_idx():
            r = self.core.rec(i)
            troop = r[6] | (r[7] << 8)
            self.tree.insert('', 'end', iid=str(i),
                             values=(i+1, nm, troop, r[25], r[23], r[24],
                                     r[17], r[18], r[19], r[20], r[21], r[22]))

    def on_select(self, _ev=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.cur_idx = int(sel[0])
        self.show_selected()

    def show_selected(self):
        if self.cur_idx is None:
            return
        idx = self.cur_idx
        self.cur_name.set('%d. %s' % (idx + 1, self.names.name(self.core.rec(idx))))
        all_specs = ([('troop', '兵力', 6, 2, 0, 65535, 'int', '')] +
                     [(k, lab, off, 1, 1, 100, 'int', '') for k, off, lab in ABIL] +
                     EXTRA_SPECS)
        for spec in all_specs:
            key = spec[0]
            if key in self.vars:
                self.vars[key].set(str(self.core.read_field(idx, spec)))
        mask = self.core.get_int(idx, 8, 2)
        ids = [i for i in range(ITEM_COUNT) if mask & (1 << i)]
        self.rebuild_item_rows(ids)

    def _read_int(self, v, lo, hi, label):
        s = v.get().strip()
        try:
            n = int(s)
        except ValueError:
            raise ValueError('%s 必须填数字' % label)
        if not (lo <= n <= hi):
            raise ValueError('%s 超出范围 %d~%d' % (label, lo, hi))
        return n

    def apply_all(self):
        if self.cur_idx is None:
            messagebox.showinfo('提示', '先在列表里选中一名武将')
            return
        idx = self.cur_idx
        all_specs = ([('troop', '兵力', 6, 2, 0, 65535, 'int', '')] +
                     [(k, lab, off, 1, 1, 100, 'int', '') for k, off, lab in ABIL] +
                     EXTRA_SPECS)
        try:
            for spec in all_specs:
                key, label, off, size, lo, hi, kind, note = spec
                if key not in self.vars:
                    continue
                v = self._read_int(self.vars[key], lo, hi, label)
                self.core.write_field(idx, spec, v)
            ids = self.collect_item_ids()
            if len(set(ids)) != len(ids):
                raise ValueError('宝物重复：同一件宝物不能放在两个格子')
            mask = 0
            for iid in ids:
                mask |= (1 << iid)
            self.core.set_int(idx, 8, mask, 2)
            if self.scn_core is not None and self.sync_var.get():
                for spec in SYNC_SPECS:
                    v = self.core.read_field(idx, spec)
                    self.scn_core.write_field(idx, spec, v)
                self.scn_dirty = True
        except ValueError as ex:
            messagebox.showerror('输入有误', str(ex))
            return
        extra = '（能力已同步到剧本 %s）' % self.scn_name if (self.scn_core is not None and self.scn_dirty) else ''
        self.status.set('已修改 %d. %s（未保存）%s' % (idx + 1, self.names.name(self.core.rec(idx)), extra))
        self.refresh()
        self.tree.selection_set(str(idx))

    def apply_batch(self):
        s = self.batch_var.get().strip()
        if not s:
            messagebox.showinfo('提示', '先填一个兵力数值')
            return
        try:
            troop = int(s)
        except ValueError:
            messagebox.showerror('输入有误', '兵力必须填数字')
            return
        if not (0 <= troop <= 65535):
            messagebox.showerror('输入有误', '兵力范围 0~65535')
            return
        items = list(self.filtered_idx())
        if not items:
            messagebox.showinfo('提示', '没有符合筛选的武将')
            return
        if not messagebox.askyesno('确认', '将 %d 名武将的兵力都设为 %d？（其它不变）' % (len(items), troop)):
            return
        for i, _ in items:
            self.core.set_int(i, 6, troop, 2)
        self.status.set('已批量设置 %d 人兵力=%d（未保存）' % (len(items), troop))
        self.refresh()

    def save_file(self):
        if self.core.path is None:
            messagebox.showinfo('提示', '还没有打开文件')
            return
        try:
            target = self.core.save()
            saved_scn = ''
            if self.scn_core is not None and self.scn_dirty:
                self.scn_core.save()
                saved_scn = '\n剧本 %s 已同步保存（原文件已备份 .bak）' % self.scn_name
        except Exception as ex:
            messagebox.showerror('保存失败', str(ex))
            return
        messagebox.showinfo('完成', '已保存 %s\n（原文件已备份为 .bak）%s' % (target, saved_scn))
        self.status.set('已保存: %s' % target)


def main():
    try:
        NameTable()
    except RuntimeError as ex:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror('缺少数据文件', str(ex))
        r.destroy()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
