#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按人工核选的 Commons 文件名重抓名作图。先下到 /tmp/fixworks/，
目检通过后由 apply_works.py 入库。

用法: python3 data/pin_works.py
"""
import json, os, sys, time, urllib.parse, urllib.request, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/tmp/fixworks"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
WIDTH = 1100

# nid -> 精确的 Commons 文件名（不含 File: 前缀）
PICKS = {
    "wu_daozi":    "送子天王图.jpg",
    "dong_yuan":   "董源潇湘图卷.png",
    "ju_ran":      "Ju Ran Seeking the Tao.jpg",
    "li_cheng":    "Li Cheng and Wang Xiao - Reading The Memorial Stele - Google Art Project.jpg",
    "su_shi":      "Su Shi-Vieil arbre et rocher étrange.jpg",
    "shen_zhou":   "Lofty Mt.Lu by Shen Zhou.jpg",
    "tang_yin":    "唐寅《秋風紈扇圖》.jpg",
    "shi_tao":     "石涛搜尽奇峰图卷.png",
    "wu_changshuo": "吴昌硕 桃实图轴.jpg",
    "qi_baishi":   "QiBaishiGarnelen.jpg",
    "xu_beihong":  "徐悲鴻 三駿圖 1941.jpg",
    "durer":       "Self-Portrait by Albrecht Dürer (5987288890).jpg",
    "vermeer":     "1665 Girl with a Pearl Earring.jpg",
    "david":       "Death of Marat by David.jpg",
    "manet":       "Edouard Manet - Luncheon on the Grass - Google Art Project.jpg",
    "renoir":      "Renoir, Pierre-Auguste - Dance at Le Moulin de la Galette, 1876.jpg",
    "klimt":       "The Kiss - Gustav Klimt - Google Cultural Institute.jpg",
    "munch":       "Edvard Munch - The Scream - Google Art Project.jpg",
    "matisse":     "Matisse - Carra, 467.jpg",
    "kandinsky":   "Vassily Kandinsky, 1923 - Composition 8, huile sur toile, 140 cm x 201 cm, Musée Guggenheim, New York.jpg",
    "duchamp":     "Duchamp Fountaine.jpg",
    "mondrian":    "Mondrian - Composition with Red, Blue and Yellow (1930).jpg",
    "picasso":     "Les Demoiselles d'Avignon (7925004644).jpg",
    "warhol":      "Andy Warhol Campbell's Soup Cans (MoMA - New York).jpg",
}

# 这些作品在 Commons 上没有合规图，改为不配图（抽屉显示「暂无可用图像」）
NO_IMAGE = ["mi_fu", "pollock", "dali"]


def get(url, tries=3, timeout=40):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(2 + 2 * i)
    raise last


def page_info(fname):
    page = ("https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(fname.replace(" ", "_")))
    try:
        h = get(page, tries=2).decode("utf-8", "ignore")
    except Exception:
        return {"license": None, "page": page, "cats": []}
    cats = []
    m = re.search(r'"wgCategories"\s*:\s*(\[[^\]]*\])', h)
    if m:
        try:
            cats = json.loads(m.group(1))
        except Exception:
            cats = []
    if not cats:
        cats = [urllib.parse.unquote(c) for c in re.findall(r'href="/wiki/Category:([^"?]+)"', h)]
    lic = None
    cl = [c.lower() for c in cats]
    if any(c.startswith(("cc0", "cc-zero", "cc-pd-mark", "public domain")) for c in cl):
        lic = "CC0" if any(c.startswith(("cc0", "cc-zero")) for c in cl) else "Public domain"
    else:
        pd = [c for c in cats if re.match(r"^PD[-_ ]", c)]
        if pd:
            lic = pd[0]
        else:
            cc = [c for c in cats if re.match(r"^CC[-_ ]BY", c)]
            if cc:
                lic = cc[0]
    return {"license": lic, "page": page, "cats": cats[:12]}


def main():
    os.makedirs(TMP, exist_ok=True)
    only = None
    if len(sys.argv) > 2 and sys.argv[1] == "--only":
        only = {s.strip() for s in sys.argv[2].split(",") if s.strip()}
    picked, failed = {}, []
    for nid, fname in PICKS.items():
        if only and nid not in only:
            continue
        info = page_info(fname)
        if not info["license"]:
            failed.append((nid, "授权不明", fname[:60]))
            print("  %-14s SKIP  %s" % (nid, fname[:60]), flush=True)
            continue
        try:
            u = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                 + urllib.parse.quote(fname.replace(" ", "_")) + "?width=%d" % WIDTH)
            data = get(u)
        except Exception as e:
            failed.append((nid, str(e)[:40], fname[:60]))
            print("  %-14s DLERR %s" % (nid, e), flush=True)
            continue
        if len(data) < 3000:
            failed.append((nid, "过小", fname[:60]))
            print("  %-14s SMALL %s" % (nid, fname[:60]), flush=True)
            continue
        with open(os.path.join(TMP, nid + ".jpg"), "wb") as f:
            f.write(data)
        picked[nid] = {
            "file": "assets/works/%s.jpg" % nid,
            "commonsFile": "File:" + fname,
            "commonsPage": info["page"],
            "license": info["license"],
            "credit": "Wikimedia Commons",
        }
        print("  %-14s OK    %-64s [%s]" % (nid, fname[:64], info["license"]), flush=True)
        time.sleep(0.3)
    with open(os.path.join(TMP, "picked.json"), "w", encoding="utf-8") as f:
        json.dump(picked, f, ensure_ascii=False, indent=1)
    print("\n候选 %d / 失败 %d" % (len(picked), len(failed)))
    for x in failed:
        print("  失败:", x)


if __name__ == "__main__":
    main()
