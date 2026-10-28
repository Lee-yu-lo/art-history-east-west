#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「名作图 / 头像」的拼图校验页，用来人工目检是否抓错图。
用法:
    python3 data/contact_sheet.py works     # 校验 assets/works
    python3 data/contact_sheet.py portraits # 校验 assets/portraits
输出: /tmp/sheet_works_N.png
"""
import json, os, sys, math
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVAIL = ROOT

CELL = 260
LABEL = 34
COLS = 5
PER_SHEET = 20

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield i, lst[i:i + n]


def build(kind, folder=None):
    if folder:
        title_src = os.path.join(ROOT, "data", "skeleton.json")
    elif kind == "works":
        folder = os.path.join(ROOT, "assets", "works")
        title_src = os.path.join(ROOT, "data", "skeleton.json")
    else:
        folder = os.path.join(ROOT, "assets", "portraits")
        title_src = os.path.join(ROOT, "data", "skeleton.json")

    skel = json.load(open(title_src, encoding="utf-8"))
    names = {n["id"]: n["name"] for n in skel["nodes"]}
    works = {n["id"]: (n.get("works") or [{}])[0].get("title", "") for n in skel["nodes"]}

    ids = sorted(f for f in os.listdir(folder) if f.endswith(".jpg"))
    ids = [i[:-4] for i in ids]
    # 按 skeleton 顺序排，方便对照
    order = [n["id"] for n in skel["nodes"] if n["id"] in ids]
    ids = order + [i for i in ids if i not in order]

    f_big = font(20)
    f_sml = font(15)
    out = []
    for si, (start, group) in enumerate(chunks(ids, PER_SHEET), 1):
        rows = int(math.ceil(len(group) / float(COLS)))
        W = COLS * CELL
        H = rows * (CELL + LABEL)
        canvas = Image.new("RGB", (W, H), (245, 245, 242))
        d = ImageDraw.Draw(canvas)
        for idx, nid in enumerate(group):
            r, c = divmod(idx, COLS)
            x, y = c * CELL, r * (CELL + LABEL)
            p = os.path.join(folder, nid + ".jpg")
            try:
                im = Image.open(p).convert("RGB")
            except Exception:
                continue
            im.thumbnail((CELL - 16, CELL - 16))
            cx = x + (CELL - im.width) // 2
            cy = y + (CELL - im.height) // 2
            canvas.paste(im, (cx, cy))
            d.rectangle([x + 1, y + 1, x + CELL - 2, y + CELL - 2], outline=(200, 200, 195))
            lbl = "%d. %s" % (start + idx + 1, nid)
            sub = (names.get(nid, "") + " · " + works.get(nid, ""))[:26]
            d.text((x + 6, y + CELL + 2), lbl, fill=(30, 30, 30), font=f_big)
            d.text((x + 6, y + CELL + 19), sub, fill=(110, 110, 110), font=f_sml)
        path = "/tmp/sheet_%s_%d.png" % (kind, si)
        canvas.save(path)
        out.append(path)
    print("共 %d 张，输出 %d 页" % (len(ids), len(out)))
    for p in out:
        print(" ", p)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    folder = None
    if args and os.path.isdir(args[-1]):
        folder = args[-1]
        args = args[:-1]
    build(args[0] if args else "works", folder=folder)
