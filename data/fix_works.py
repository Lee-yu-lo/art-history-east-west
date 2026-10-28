#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定点重抓名作图。Commons action API 被限流（429/503），改走 HTML 检索页。
先下到 /tmp/fixworks/ 目检，确认无误后再入库 assets/works。

用法:
    python3 data/fix_works.py            # 抓 FETCH 表里所有缺的
    python3 data/fix_works.py --only a,b # 只抓指定节点
"""
import json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/tmp/fixworks"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
WIDTH = 1100

# nid -> (多组检索词, 标题里必须出现的词(小写, 任一), 标题里不能出现的词)
FETCH = {
    "wu_daozi":    (["Wu Daozi Heavenly King", "送子天王图"], ("song", "heavenly", "送子"), ()),
    "dong_yuan":   (["Dong Yuan Xiao Xiang rivers", "董源 潇湘图"], ("xiaoxiang", "xiao xiang", "dong yuan", "潇湘"), ("school", "park")),
    "ju_ran":      (["Juran painting Song", "巨然 秋山问道图"], ("juran", "ju ran", "巨然", "autumn"), ()),
    "li_cheng":    (["Li Cheng Buddhist temple stele", "读碑窠石图"], ("li cheng", "李成", "stele", "碑"), ("station", "street")),
    "su_shi":      (["Su Shi Wood and Rock", "枯木怪石图 苏轼"], ("wood", "rock", "枯木", "su shi"), ()),
    "mi_fu":       (["Mi Fu landscape Song", "米芾 春山瑞松图"], ("mi fu", "米芾", "landscape"), ("square", "plaza", "archway")),
    "shen_zhou":   (["Shen Zhou Lofty Mount Lu", "沈周 庐山高图"], ("lu", "shen zhou", "沈周", "mount"), ("school", "singer")),
    "tang_yin":    (["Tang Yin Autumn Wind fan", "唐寅 秋风纨扇图"], ("tang yin", "唐寅", "autumn", "fan"), ()),
    "shi_tao":     (["Shitao searching mountains", "石涛 搜尽奇峰"], ("shitao", "shi tao", "石涛", "mountain"), ("postcard", "stamp")),
    "ren_bonian":  (["Ren Bonian painting", "任伯年 画像"], ("ren", "任", "portrait"), ("fan", "folding")),
    "wu_changshuo": (["Wu Changshuo painting peony prunus", "吴昌硕 花"], ("wu changshuo", "吴昌硕", "peony", "prunus", "plum"), ("garden", "pavilion", "hall")),
    "qi_baishi":   (["Qi Baishi shrimp frogs painting", "齐白石 虾"], ("qi baishi", "齐白石", "shrimp", "frog", "虾"), ("crater", "moon", "mars")),
    "xu_beihong":  (["Xu Beihong horse ink", "徐悲鸿 马"], ("xu beihong", "徐悲鸿", "horse", "马"), ("stamp", "poster", "statue", "park", "museum building")),
    "durer":       (["Albrecht Dürer self-portrait 1500"], ("self", "1500", "dürer", "durer"), ("inscription", "detail")),
    "vermeer":     (["Girl with a Pearl Earring Vermeer"], ("pearl", "girl", "meisje"), ("museum", "wall", "room", "visitor", "exhibit")),
    "david":       (["Death of Marat David"], ("marat",), ("hand", "detail", "letter only")),
    "manet":       (["Le déjeuner sur l'herbe Manet", "Manet Luncheon on the Grass"], ("déjeuner", "dejeuner", "luncheon", "grass"), ("museum", "visitor", "wall", "people in front")),
    "renoir":      (["Bal du moulin de la Galette Renoir"], ("moulin", "galette", "bal"), ("museum", "wall", "visitor", "exhibit")),
    "klimt":       (["The Kiss Gustav Klimt"], ("kiss", "klimt"), ("skull", "rhino", "bone", "museum", "wall")),
    "munch":       (["The Scream Edvard Munch painting"], ("scream", "munch", "skrik"), ("museum", "wall", "visitor", "exhibit", "stamp")),
    "matisse":     (["Matisse La Danse Barnes", "Matisse Dance 1910"], ("dance", "danse", "matisse"), ("arch", "sculpture", "museum", "wall", "visitor")),
    "picasso":     (["Les Demoiselles d'Avignon Picasso painting"], ("demoiselles", "avignon"), ("cosplay", "makeup", "face paint", "museum", "visitor")),
    "kandinsky":   (["Kandinsky Composition VIII 1923"], ("composition", "viii", "8", "kandinsky"), ("vii", "7", "museum", "visitor")),
    "duchamp":     (["Fountain Duchamp urinal"], ("fountain", "urinal", "mutt"), ("label", "plaque", "museum text", "wall text")),
    "dali":        (["The Persistence of Memory Dalí painting MoMA"], ("persistence", "memory", "dalí", "dali"), ("pendant", "jewellery", "jewelry", "silver", "sculpture", "3d")),
    "pollock":     (["Autumn Rhythm Number 30 Pollock Metropolitan"], ("autumn", "rhythm", "pollock", "number 30"), ("mountain", "landscape photo", "forest", "autumn mountain")),
    "warhol":      (["Campbell's Soup Cans Warhol 1962 MoMA"], ("campbell", "soup", "warhol"), ("stamp", "postage", "wall text", "museum building")),
    "mondrian":    (["Mondrian Composition with Red Blue and Yellow 1930"], ("composition", "red", "blue", "yellow", "mondrian"), ("museum", "visitor", "wall")),
}

# 明显不是画作的文件名
BAD = re.compile(r"(\bdetail\b|\bcrop|\bfragment\b|\bx-?ray\b|\bverso\b|\breverse\b|"
                 r"\bphotograph of\b|photo of the\b|\bframe\b|\bframeless\b|\bsignature\b|"
                 r"\binscription\b|\bseal\b|\bcolophon\b|\bstamp\b|\bpostage\b|\bbanknote\b|"
                 r"\bcoin\b|\bcover\b|\bposter\b|\blogo\b|\bicon\b|\bmap of\b|\bdiagram\b|"
                 r"\bscreenshot\b|\bpanorama\b|\bin situ\b|\bon display\b|"
                 r"\bmuseum (interior|hall|room)\b|\bexhibition\b|\bexhibit\b|"
                 r"\bvisitors?\b|\btourists?\b|\bstatue\b|\bbust\b|\btomb\b|\bgrave\b|"
                 r"\bstreet\b|\bbuilding\b|\bpark\b|\bschool\b|\bstation\b|\bplaza\b|"
                 r"\bcrater\b|\bmoon\b|\bmars\b|\bskull\b|\bbone\b|\bskeleton\b|"
                 r"\bsculpture\b|\barch\b|\bjewell?ery\b|\bpendant\b|\bsilver\b|"
                 r"\bcosplay\b|\bmakeup\b|\bface ?paint\b|\bportrait of the artist\b|\bphoto\b)", re.I)


def get(url, tries=3, timeout=35):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                          timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(2 + 2 * i)
    raise last


def search(q):
    u = ("https://commons.wikimedia.org/w/index.php?search="
         + urllib.parse.quote(q) + "&ns6=1&limit=25")
    h = get(u).decode("utf-8", "ignore")
    out = []
    for t in re.findall(r'title="File:([^"]+)"', h):
        t = urllib.parse.unquote(t)
        if "page does not exist" in t:
            continue
        if t not in out:
            out.append(t)
    return out


def commons_cats(fname):
    page = ("https://commons.wikimedia.org/wiki/File:"
            + urllib.parse.quote(fname.replace(" ", "_")))
    try:
        h = get(page, tries=2).decode("utf-8", "ignore")
    except Exception:
        return [], page
    cats = []
    m = re.search(r'"wgCategories"\s*:\s*(\[[^\]]*\])', h)
    if m:
        try:
            cats = json.loads(m.group(1))
        except Exception:
            cats = []
    if not cats:
        cats = [urllib.parse.unquote(c) for c in re.findall(r'href="/wiki/Category:([^"?]+)"', h)]
    return cats, page


def ok_license(cats):
    cl = [c.lower() for c in cats]
    if any(c.startswith(("cc0", "cc-pd-mark", "public domain")) for c in cl):
        return "Public domain"
    pd = [c for c in cats if re.match(r"^PD[-_ ]", c)]
    if pd:
        return pd[0]
    cc = [c for c in cats if re.match(r"^CC[-_ ]BY", c)]
    if cc:
        return cc[0]
    return None


def score(fname, need, forbid):
    f = fname.lower()
    if BAD.search(f):
        return -1
    for b in forbid:
        if b in f:
            return -1
    if need and not any(n in f for n in need):
        return 0.5
    return 1.0


def fetch(nid, save=None):
    spec = FETCH[nid]
    queries, need, forbid = spec
    best = None
    for q in queries:
        try:
            cand = search(q)
        except Exception as e:
            print("  %-14s 检索失败 %s" % (nid, e), flush=True)
            continue
        ranked = []
        for f in cand:
            s = score(f, need, forbid)
            if s > 0:
                ranked.append((s, f))
        ranked.sort(key=lambda x: -x[0])
        if ranked:
            best = ranked[0][1]
            break
        time.sleep(0.5)
    if not best:
        print("  %-14s MISS" % nid, flush=True)
        return None
    cats, page = commons_cats(best)
    lic = ok_license(cats)
    if not lic:
        print("  %-14s SKIP 授权不明 %s" % (nid, best[:60]), flush=True)
        return None
    out = os.path.join(TMP, (save or nid) + ".jpg")
    u = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
         + urllib.parse.quote(best.replace(" ", "_")) + "?width=%d" % WIDTH)
    data = get(u)
    if len(data) < 3000:
        print("  %-14s 文件过小" % nid, flush=True)
        return None
    with open(out, "wb") as fo:
        fo.write(data)
    print("  %-14s OK  %s  [%s]" % (nid, best[:70], lic), flush=True)
    return {"file": "assets/works/%s.jpg" % nid, "commonsFile": "File:" + best,
            "commonsPage": page, "license": lic, "credit": "Wikimedia Commons"}


def main():
    os.makedirs(TMP, exist_ok=True)
    only = None
    if len(sys.argv) > 2 and sys.argv[1] == "--only":
        only = {s.strip() for s in sys.argv[2].split(",") if s.strip()}
    man = json.load(open(os.path.join(ROOT, "assets", "works", "manifest.json"), encoding="utf-8"))
    picked = {}
    for nid in FETCH:
        if only and nid not in only:
            continue
        r = fetch(nid)
        if r:
            picked[nid] = r
        time.sleep(0.3)
    with open(os.path.join(TMP, "picked.json"), "w", encoding="utf-8") as f:
        json.dump(picked, f, ensure_ascii=False, indent=1)
    print("\n候选 %d/%d → %s" % (len(picked), len(FETCH if not only else only), TMP))


if __name__ == "__main__":
    main()
