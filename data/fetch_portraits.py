#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取画家肖像（头像）。

采集链路（2026-10 实测：w/api.php 与 api.wikimedia.org 在部分网络下返回 503，
因此全部改用「静态 / REST」端点）：
  1) QID    : Wikipedia REST  /api/rest_v1/page/summary/<title>  -> wikibase_item
  2) P18    : Wikidata 静态   /wiki/Special:EntityData/<QID>.json
  3) 授权   : Commons 文件页 HTML 里的 wgCategories（PD-* / CC-PD-Mark / CC0 / CC BY*）
  4) 下载   : Commons        /wiki/Special:FilePath/<file>?width=N

只接受 PD / CC0 / CC BY / CC BY-SA。逐张记录来源与授权。
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OUTDIR = os.path.join(ROOT, "assets", "portraits")
MANIFEST = os.path.join(OUTDIR, "manifest.json")
WIDTH = 400

# 明显不是人物肖像的题材
BAD_HINT = ("tomb", "grave", "monument", "statue", "bust", "plaque", "memorial",
            "house", "museum", "signature", "street", "plaza", "coat of arms",
            "house where", "birthplace", "tombstone", "memorial plate")


def get(url, tries=4, timeout=40):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(2 + 3 * i)
    raise last


def jget(url):
    return json.loads(get(url).decode("utf-8"))


# ---------- 1) QID ----------
def rest_summary(title, lang):
    """Wikipedia REST summary，返回 (qid, originalimage_file_or_None)。"""
    u = ("https://%s.wikipedia.org/api/rest_v1/page/summary/%s"
         % (lang, urllib.parse.quote(title.replace(" ", "_"), safe="")))
    try:
        d = jget(u)
    except Exception:
        return None, None
    qid = d.get("wikibase_item")
    img = None
    oi = d.get("originalimage") or {}
    src = oi.get("source") or ""
    m = re.search(r"/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", src)
    if m:
        img = urllib.parse.unquote(m.group(1))
        img = re.sub(r"^\d+px-", "", img)
    elif "/wiki/Special:FilePath/" in src:
        img = urllib.parse.unquote(src.split("Special:FilePath/")[-1].split("?")[0])
    return qid, img


# ---------- 2) Wikidata ----------
def entity(qid):
    d = jget("https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid)
    ents = d.get("entities") or {}
    return list(ents.values())[0] if ents else None


def claim_ids(e, pid):
    ids = []
    for c in (e.get("claims") or {}).get(pid) or []:
        try:
            ids.append(c["mainsnak"]["datavalue"]["value"]["id"])
        except Exception:
            pass
    return ids


def p18_all(e):
    out = []
    for c in (e.get("claims") or {}).get("P18") or []:
        try:
            out.append(c["mainsnak"]["datavalue"]["value"])
        except Exception:
            pass
    return out


def is_painter(e):
    painter_q = {"Q1028181", "Q483501", "Q1281618", "Q1114461", "Q33231", "Q15296811"}
    if painter_q & set(claim_ids(e, "P106")):
        return True
    for lang in ("en", "zh", "de"):
        d = ((e.get("descriptions") or {}).get(lang) or {}).get("value", "").lower()
        if any(k in d for k in ("painter", "artist", "画家", "maler", "peintre", "pintor")):
            return True
    return False


# ---------- 3) 授权：Commons 文件页 wgCategories ----------
def classify_license(cats):
    cats_l = [c.lower() for c in cats]
    joined = " | ".join(cats)
    if any(c.startswith("cc0") for c in cats_l):
        return "CC0", True
    if any(c.startswith("cc-pd-mark") or c.startswith("public domain") for c in cats_l):
        return "Public domain", True
    pd = [c for c in cats if re.match(r"^PD[-_ ]", c)]
    if pd:
        return pd[0], True
    cc = [c for c in cats if re.match(r"^CC[-_ ]BY", c)]
    if cc:
        return cc[0], True
    return (joined[:80] if joined else "?"), False


def commons_info(fname):
    """返回 dict(license, ok, cats, page)。"""
    page = "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(fname.replace(" ", "_"))
    try:
        h = get(page, tries=3, timeout=40).decode("utf-8", "ignore")
    except Exception:
        return {"license": "?", "ok": False, "cats": [], "page": page}
    cats = []
    m = re.search(r'"wgCategories"\s*:\s*(\[[^\]]*\])', h)
    if m:
        try:
            cats = json.loads(m.group(1))
        except Exception:
            cats = []
    if not cats:
        cats = re.findall(r'href="/wiki/Category:([^"?]+)"', h)
        cats = [urllib.parse.unquote(c) for c in cats]
    lic, ok = classify_license(cats)
    return {"license": lic, "ok": ok, "cats": cats, "page": page}


# ---------- 4) 下载 ----------
def download(fname, out, width=WIDTH):
    url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
           + urllib.parse.quote(fname.replace(" ", "_")) + "?width=" + str(width))
    data = get(url)
    if len(data) < 1500:
        return None
    with open(out, "wb") as f:
        f.write(data)
    return data


def size_of(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        try:
            import struct
            d = open(path, "rb").read()
            i = 2
            while i < len(d):
                if d[i] != 0xFF:
                    i += 1
                    continue
                mk = d[i + 1]
                if mk in (0xC0, 0xC1, 0xC2):
                    h = struct.unpack(">H", d[i + 5:i + 7])[0]
                    w = struct.unpack(">H", d[i + 7:i + 9])[0]
                    return (w, h)
                if mk in (0xD8, 0xD9) or 0xD0 <= mk <= 0xD7:
                    i += 2
                    continue
                ln = struct.unpack(">H", d[i + 2:i + 4])[0]
                i += 2 + ln
        except Exception:
            pass
    return (0, 0)


def kind_of(fn):
    f = fn.lower()
    if "self-portrait" in f or "selfportrait" in f or "self portrait" in f or "selbstbildnis" in f:
        return "selfportrait"
    if any(k in f for k in ("foto", "photo", "photograph", "photographie")):
        return "photo"
    return "portrait"


def cache_load(name):
    p = os.path.join(ROOT, "data", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def cache_save(name, obj):
    with open(os.path.join(ROOT, "data", name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    skel = json.load(open(os.path.join(ROOT, "data", "skeleton.json"), encoding="utf-8"))

    # 站点里尚未收录、但后续可能补进来的画家
    extra = {
        "guan_tong": ("Guan Tong", "关仝"), "liu_songnian": ("Liu Songnian", "刘松年"),
        "wu_zhen": ("Wu Zhen (painter)", "吴镇"), "wang_meng": ("Wang Meng (painter)", "王蒙"),
        "kun_can": ("Kuncan", "髡残"), "lin_fengmian": ("Lin Fengmian", "林风眠"),
        "hongren": ("Hongren (painter)", "弘仁"),
        "velazquez": ("Diego Velázquez", "委拉斯开兹"), "goya": ("Francisco Goya", "戈雅"),
        "malevich": ("Kazimir Malevich", "马列维奇"),
    }
    targets = [(n["id"], n.get("nameEn") or "", n["name"], n.get("tradition")) for n in skel["nodes"]]
    have = {t[0] for t in targets}
    for k, (en, zh) in extra.items():
        if k not in have:
            targets.append((k, en, zh, "west" if k in ("velazquez", "goya", "malevich") else "china"))

    mani = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    todo = [t for t in targets if t[0] not in mani]
    if not todo:
        print("全部已抓取")
        return

    # 1) QID + Wikipedia 首图（双候选）。每 8 个落一次盘，中断可续跑。
    print("解析 QID / 候选图 …", flush=True)
    cand = cache_load(".portrait_cand.json")
    need = [t for t in todo if t[0] not in cand]
    for idx, (nid, en, zh, trad) in enumerate(need):
        opts = []
        base = en.split(" (")[0] if en else ""
        # 西方：英文名优先；中国：中文名优先，英文名兜底
        order = [(base, "en"), (zh, "zh")] if trad == "west" else [(zh, "zh"), (base, "en")]
        seen_q = []
        for title, lang in order:
            if not title:
                continue
            try:
                q, img = rest_summary(title, lang)
            except Exception:
                q, img = None, None
            if q and q not in seen_q:
                seen_q.append(q)
            if img:
                opts.append((img, "wiki:" + lang + ":" + title))
            time.sleep(0.15)
        # Wikidata P18（首选）
        p18 = []
        for q in seen_q:
            try:
                e = entity(q)
            except Exception:
                time.sleep(1.0)
                continue
            if not e or not is_painter(e):
                continue
            for f in p18_all(e):
                p18.append((f, "wikidata:" + q))
            time.sleep(0.15)
        cand[nid] = {"p18": p18[:3], "wiki": opts[:3], "qids": seen_q}
        print("  [%d/%d] %-16s qid=%s p18=%d wiki=%d"
              % (idx + 1, len(need), nid, ",".join(seen_q) or "-", len(p18), len(opts)), flush=True)
        if (idx + 1) % 8 == 0:
            cache_save(".portrait_cand.json", cand)
    cache_save(".portrait_cand.json", cand)

    # 2) 逐个挑第一张「授权合规 + 不像作品」的图
    print("\n校验授权并下载 …", flush=True)
    missing = {}
    for nid, en, zh, trad in todo:
        c = cand.get(nid) or {}
        opts = (c.get("p18") or []) + (c.get("wiki") or [])
        picked = None
        for fn, via in opts:
            if any(b in fn.lower() for b in BAD_HINT):
                continue
            info = commons_info(fn)
            if not info["ok"]:
                continue
            picked = (fn, via, info)
            break
        if not picked:
            missing[nid] = "无合规授权的候选图"
            print("  %-16s MISS" % nid, flush=True)
            continue
        fn, via, info = picked
        out = os.path.join(OUTDIR, nid + ".jpg")
        try:
            if not download(fn, out):
                missing[nid] = "下载文件过小"
                print("  %-16s DL-SMALL" % nid, flush=True)
                continue
        except Exception as e:
            missing[nid] = "下载失败"
            print("  %-16s DLERR" % nid, flush=True)
            continue
        w, h = size_of(out)
        mani[nid] = {
            "file": "assets/portraits/" + nid + ".jpg",
            "commonsFile": fn, "commonsPage": info["page"],
            "license": info["license"], "credit": "Wikimedia Commons",
            "kind": kind_of(fn), "via": via, "w": w, "h": h,
        }
        print("  %-16s OK %-12s %dx%d  %s" % (nid, mani[nid]["kind"], w, h, fn[:46]), flush=True)
        time.sleep(0.2)

    if missing:
        mani["_missing"] = missing
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(mani, f, ensure_ascii=False, indent=1)
    ok = len([k for k in mani if not k.startswith("_")])
    tot = sum(os.path.getsize(os.path.join(ROOT, mani[k]["file"]))
              for k in mani if not k.startswith("_") and os.path.exists(os.path.join(ROOT, mani[k]["file"])))
    print("\n肖像 %d/%d  容量 %.2f MB  缺失 %d" % (ok, len(targets), tot / 1048576.0, len(missing)), flush=True)


if __name__ == "__main__":
    main()
