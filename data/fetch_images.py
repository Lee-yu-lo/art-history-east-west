#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_images.py — 中西方美术史可视化导读网站 · 名画素材抓取脚本

从 Wikimedia Commons 检索并下载公有领域 / CC 授权的名画扫描件。
严禁 AI 生成：本脚本只做检索 + 下载 + 压缩，不生成任何图像。

用法:
    python3 fetch_images.py                # 全量跑（跳过已存在的文件）
    python3 fetch_images.py --dry-run      # 只检索，不下载，打印候选与命中情况
    python3 fetch_images.py --only a,b,c   # 只跑指定 node_id
    python3 fetch_images.py --force        # 强制重新下载
"""

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKELETON = os.path.join(ROOT, "data", "skeleton.json")
OUTDIR = os.path.join(ROOT, "assets", "works")
MANIFEST = os.path.join(OUTDIR, "manifest.json")

UA = "ArtHistoryEduFetcher/1.0 (educational static site; contact: local-dev) python-urllib"
API = "https://commons.wikimedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

MIN_W = 500          # 原图最小宽度
TARGET_W = 900       # 下载缩略图宽度
MAX_BYTES = 300 * 1024
QUALITY = 82

OK_LICENSE_PREFIX = (
    "public domain", "pd", "cc0", "cc by", "cc-by", "no restrictions",
)

BAD_NAME_RE = re.compile(
    r"(\bdetail\b|\bcrop|\bfragment|\bx-?ray|\binfrared|\braking light|"
    r"\brestoration|\bbefore\b.*\bclean|\bphotograph of|photo of the|"
    r"\bframe\b|\bsignature\b|\binscription\b|\bseal\b|\bcolophon\b|"
    r"\bverso\b|\breverse\b|\bstudy for\b|\bpreparatory\b|\bcartoon\b|"
    r"\bcopy after\b|\bwatermark|\blogo\b|\bicon\b|\bstamp\b|\bbanknote\b|"
    r"\bcoin\b|\bcover\b|\bposter\b|\bmap of\b|\bdiagram\b|\bchart\b|"
    r"\bwikipedia\b|\bscreenshot|\bpanorama of the room|\bin situ\b|"
    r"\bon display\b|\bmuseum (interior|hall|room)|\bgrayscale\b|"
    r"\bblack and white (photo|photograph)|\bb&w\b|"
    # 与画作本身无关的衍生场景
    r"\bgrave\b|\btomb\b|\bcemetery\b|\bmonument\b|\bmemorial\b|\bplaque\b|"
    r"\bbirthplace\b|\bbirth house\b|\bstatue\b|\bbust\b|\bstreet\b|\bsign\b|"
    r"\bexhibition\b|\bexhibit\b|\bvisitors?\b|\btourists?\b)",
    re.I,
)

PARTIAL_RE = re.compile(
    r"(\bsection\b|\bpart\b|\bportion\b|\bextract\b|\bdetails?\b|\bcrop|"
    r"\bfragment\b|\b局部\b|\bsegment\b|\bdetail\b|\bscroll \d\b|\bfolio\b|"
    r"\bhalf\b|\b卷\b|\bpanel\b|\bfolio\b)",
    re.I,
)

EXT_OK = (".jpg", ".jpeg", ".png")


# ----------------------------------------------------------------------------
# 网络工具
# ----------------------------------------------------------------------------
def http_get(url, timeout=45):
    """用 curl 发请求，带合规 UA，返回 bytes；失败返回 None。"""
    cmd = ["curl", "-sSL", "--compressed", "-A", UA,
           "--max-time", str(timeout), url]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
        if p.returncode != 0:
            return None
        return p.stdout
    except Exception:
        return None


def commons_search(query, limit=10, tries=4):
    """Commons 搜索 API，返回候选文件列表。自带限流退避重试。"""
    qs = urllib.parse.urlencode({
        "action": "query", "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|ObjectName|Credit|LicenseUrl",
    })
    url = f"{API}?{qs}"
    for attempt in range(tries):
        raw = http_get(url)
        if raw:
            try:
                data = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                data = {}
            if "error" not in data:
                pages = (data.get("query") or {}).get("pages") or {}
                out = []
                for _pid, pg in pages.items():
                    ii = (pg.get("imageinfo") or [None])[0]
                    if not ii:
                        continue
                    out.append({
                        "title": pg.get("title", ""),   # "File:xxx.jpg"
                        "w": ii.get("width", 0) or 0,
                        "h": ii.get("height", 0) or 0,
                        "url": ii.get("url", ""),
                        "meta": ii.get("extmetadata") or {},
                    })
                return out
        # 失败或 cirrussearch-too-busy -> 退避重试
        time.sleep(1.0 * (attempt + 1))
    return []


# ----------------------------------------------------------------------------
# 清洗 / 过滤 / 评分
# ----------------------------------------------------------------------------
TAG_RE = re.compile(r"<[^>]+>")


def clean(s):
    if not s:
        return ""
    s = TAG_RE.sub("", str(s))
    s = (s.replace("&amp;", "&").replace("&nbsp;", " ")
          .replace("&quot;", '"').replace("&#039;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def meta_val(meta, key):
    v = meta.get(key)
    if isinstance(v, dict):
        return clean(v.get("value", ""))
    return ""


def norm(s):
    """小写 + 去变音符 + 非字母数字转空格，用于 token 匹配。"""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", s.lower()).strip()


def license_ok(lic):
    if not lic:
        return False
    l = lic.lower().strip()
    if l in ("", "unknown", "see below"):
        return False
    if "fair use" in l or "non-free" in l or "nonfree" in l:
        return False
    return any(l.startswith(p) for p in OK_LICENSE_PREFIX)


def is_partial_name(name):
    return bool(PARTIAL_RE.search(name or ""))


def basic_filters(c):
    """基础可用性过滤。返回 (ok, reason)"""
    t = c["title"]
    fname = t.replace("File:", "")
    low = fname.lower()
    if not low.endswith(EXT_OK):
        return False, "非 jpg/png"
    if c["w"] < MIN_W or c["h"] < 120:
        return False, f"尺寸过小 {c['w']}x{c['h']}"
    if BAD_NAME_RE.search(fname):
        return False, "命中排除词(detail/crop/frame...)"
    lic = meta_val(c["meta"], "LicenseShortName")
    if not license_ok(lic):
        return False, f"授权不可商用: {lic or '未知'}"
    return True, ""


def artist_tokens(name_en):
    """从画家英文名提取可用于匹配的 token。"""
    base = re.sub(r"\s*\(.*?\)", "", name_en or "").strip()
    toks = [t for t in norm(base).split() if len(t) > 2]
    return toks


def score(c, toks, prefer_partial=False, title_toks=()):
    fname = c["title"].replace("File:", "")
    n = norm(fname)
    s = 0.0
    # 画家名命中
    hit = sum(1 for t in toks if t in n)
    s += 5 * min(hit, 2)
    # 画名命中
    th = sum(1 for t in title_toks if t in n)
    s += 2.5 * min(th, 3)
    # 分辨率（够大加分，过大略降权避免奇怪的超高扫描件）
    s += min(c["w"], 6000) / 1500.0
    # 长宽比合理度
    ar = c["w"] / max(c["h"], 1)
    if 1.0 <= ar <= 4.0:
        s += 4
    elif ar <= 8.0:
        s += 1
    else:
        s -= 3
    # 局部/全卷取舍
    p = is_partial_name(fname) or ar > 8
    if prefer_partial:
        if p and 1.0 <= ar <= 4.5:
            s += 8
        elif p:
            s += 2
        else:
            s -= 6
    else:
        if p:
            s -= 6
    # 常见高质量版本命名
    if re.search(r"(full|complete|entire|whole|overall)", n):
        s += 2
    return s


def pick(cands, toks, title_toks=(), prefer_partial=False):
    if not cands:
        return None
    return max(cands, key=lambda c: score(c, toks, prefer_partial, title_toks))


# ----------------------------------------------------------------------------
# 查询词生成
# ----------------------------------------------------------------------------
OVERRIDES = {
    "gu_kaizhi": ["Nymph of the Luo River", "洛神賦圖", "洛神赋图", "Gu Kaizhi"],
    "zhan_ziquian": ["Zhan Ziqian", "游春圖", "游春图", "Spring Outing Zhan Ziqian"],
    "yan_lib": ["Yan Liben", "步輦圖", "步辇图", "Emperor Taizong Receiving Tibetan Envoy"],
    "wu_daozi": ["Wu Daozi", "送子天王圖", "送子天王图", "Wu Daozi Birth of Buddha"],
    "wang_wei": ["Wangchuan", "輞川圖", "辋川图", "Wang Wei Tang dynasty painting"],
    "jing_hao": ["Jing Hao", "匡廬圖", "匡庐图", "Kuanglu Tu"],
    "dong_yuan": ["Dong Yuan", "瀟湘圖", "潇湘图", "Xiaoxiang Tu"],
    "ju_ran": ["Juran", "秋山問道圖", "秋山问道图", "Qiushan Wendao"],
    "li_cheng": ["Li Cheng painter", "讀碑窠石圖", "读碑窠石图", "Li Cheng stele"],
    "fan_kuan": ["Travelers among Streams and Mountains", "谿山行旅圖", "溪山行旅图"],
    "guo_xi": ["Early Spring Guo Xi", "早春圖", "早春图"],
    "zhang_zeduan": ["Along the River During the Qingming Festival", "清明上河圖", "清明上河图"],
    "zhao_ji": ["Auspicious Cranes", "瑞鶴圖", "瑞鹤图", "Emperor Huizong"],
    "wang_ximeng": ["A Thousand Li of Rivers and Mountains", "千里江山圖", "千里江山图"],
    "li_tang": ["Wind in Pines Among a Myriad Valleys", "萬壑松風圖", "万壑松风图", "Li Tang"],
    "ma_yuan": ["Ma Yuan painter", "踏歌圖", "踏歌图", "Ma Yuan dancing singing"],
    "xia_gui": ["Xia Gui", "溪山清遠圖", "溪山清远图", "Pure and Remote Views of Streams and Mountains"],
    "su_shi": ["Su Shi painting", "枯木怪石圖", "枯木怪石图", "Withered Tree and Strange Rock"],
    "mi_fu": ["Mi Fu", "春山瑞松圖", "春山瑞松图", "Chunshan Ruisong"],
    "liang_kai": ["Liang Kai", "潑墨仙人圖", "泼墨仙人图", "Immortal in Splashed Ink"],
    "zhao_mengfu": ["Autumn Colors on the Qiao and Hua Mountains", "鵲華秋色圖", "鹊华秋色图"],
    "huang_gongwang": ["Dwelling in the Fuchun Mountains", "富春山居圖", "富春山居图"],
    "ni_zan": ["Ni Zan", "漁莊秋霽圖", "渔庄秋霁图", "Fishing Village in Autumn"],
    "shen_zhou": ["Lofty Mount Lu", "廬山高圖", "庐山高图", "Shen Zhou"],
    "wen_zhengming": ["Wen Zhengming", "真賞齋圖", "真赏斋图", "Zhenshang Zhai"],
    "tang_yin": ["Tang Yin", "秋風紈扇圖", "秋风纨扇图", "Autumn Wind and Round Fan"],
    "qiu_ying": ["Spring Morning in the Han Palace", "Qiu Ying Han Palace",
                 "漢宮春曉圖", "汉宫春晓图", "Ch'iu Ying"],
    "pollock": ["Autumn Rhythm Pollock", "Number 30 Autumn Rhythm"],
    "dali": ["The Persistence of Memory", "La persistencia de la memoria Dalí"],
    "warhol": ["Campbell's Soup Cans Warhol", "Campbell Soup Cans Andy Warhol"],
    "ren_bonian": ["Ren Bonian", "Ren Yi painter", "酸寒尉像", "任伯年"],
    "dong_qichang": ["Dong Qichang", "秋興八景圖", "秋兴八景图", "Eight Views of Autumn"],
    "xu_wei": ["Xu Wei painter", "墨葡萄圖", "墨葡萄图", "Ink Grapes Xu Wei"],
    "bada_shanren": ["Bada Shanren", "荷花小鳥圖", "荷花小鸟图", "Lotus and Birds Bada Shanren"],
    "shi_tao": ["Shitao", "搜盡奇峰打草稿", "搜尽奇峰打草稿", "Soujin Qifeng"],
    "ren_bonian": ["Ren Bonian", "酸寒尉像", "Portrait of Wu Changshuo Ren Bonian", "Ren Xiong painter"],
    "wu_changshuo": ["Wu Changshuo", "桃實圖", "桃实图", "Wu Changshuo peaches"],
    "qi_baishi": ["Qi Baishi", "蛙聲十里出山泉", "蛙声十里出山泉", "Qi Baishi tadpoles"],
    "xu_beihong": ["Xu Beihong", "奔馬圖", "奔马图", "Xu Beihong galloping horse"],

    "giotto": ["Giotto Lamentation Scrovegni", "Giotto"],
    "van_eyck": ["Arnolfini Portrait", "Jan van Eyck"],
    "botticelli": ["Birth of Venus Botticelli"],
    "leonardo": ["Mona Lisa Leonardo da Vinci"],
    "michelangelo": ["Creation of Adam Michelangelo"],
    "raphael": ["School of Athens Raphael"],
    "titian": ["Venus of Urbino Titian"],
    "durer": ["Albrecht Dürer Self-Portrait 1500", "Dürer self portrait 1500"],
    "bruegel": ["Hunters in the Snow Bruegel", "Jagers in de sneeuw Bruegel"],
    "caravaggio": ["Calling of Saint Matthew Caravaggio"],
    "rubens": ["Rape of the Daughters of Leucippus Rubens"],
    "rembrandt": ["Night Watch Rembrandt", "De Nachtwacht"],
    "vermeer": ["Girl with a Pearl Earring Vermeer"],
    "poussin": ["Et in Arcadia ego Poussin"],
    "watteau": ["Embarkation for Cythera Watteau", "Pèlerinage à l'île de Cythère"],
    "david": ["Death of Marat David"],
    "ingres": ["La Source Ingres"],
    "delacroix": ["Liberty Leading the People Delacroix"],
    "turner": ["Fighting Temeraire Turner"],
    "friedrich": ["Wanderer above the Sea of Fog"],
    "courbet": ["Burial at Ornans Courbet", "Un enterrement à Ornans"],
    "millet": ["The Gleaners Millet", "Des glaneuses Millet"],
    "manet": ["Luncheon on the Grass Manet", "Déjeuner sur l'herbe"],
    "monet": ["Impression Sunrise Monet"],
    "renoir": ["Bal du moulin de la Galette Renoir"],
    "degas": ["Dance Class Degas", "La classe de danse Degas"],
    "cezanne": ["Mont Sainte-Victoire Cézanne"],
    "vangogh": ["Starry Night Van Gogh", "De sterrennacht"],
    "gauguin": ["Where Do We Come From Gauguin", "D'où venons-nous"],
    "seurat": ["Sunday Afternoon Island La Grande Jatte Seurat"],
    "klimt": ["The Kiss Klimt", "Der Kuss Klimt"],
    "munch": ["The Scream Munch", "Skrik Munch"],
    "matisse": ["La Danse Matisse", "Dance Matisse"],
    "picasso": ["Les Demoiselles d'Avignon"],
    "kandinsky": ["Kandinsky Composition VIII"],
    "mondrian": ["Mondrian Composition with Red Blue and Yellow"],
    "duchamp": ["Fountain Duchamp"],
    "dali": ["The Persistence of Memory Dalí", "La persistencia de la memoria"],
    "pollock": ["Autumn Rhythm Pollock"],
    "warhol": ["Campbell's Soup Cans Warhol"],
}


def build_queries(node):
    nid = node["id"]
    w = node["works"][0]
    qs = []
    if nid in OVERRIDES:
        qs += OVERRIDES[nid]
    qs.append(w.get("titleEn", ""))
    qs.append(re.sub(r"（.*?）", "", w.get("title", "")).strip())
    seen, uniq = set(), []
    for q in qs:
        q = (q or "").strip()
        if q and q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq


# ----------------------------------------------------------------------------
# 下载 + 压缩
# ----------------------------------------------------------------------------
def download(file_title, dest):
    fname = file_title.replace("File:", "")
    enc = urllib.parse.quote(fname.replace(" ", "_"), safe="")
    url = f"{FILEPATH}{enc}?width={TARGET_W}"
    data = http_get(url, timeout=90)
    if not data or len(data) < 2000:
        return False, url
    with open(dest, "wb") as f:
        f.write(data)
    return True, url


def compress(dest):
    """压到宽 900 / 质量 82，单张 < 300KB。返回 (w, h, bytes)。"""
    try:
        im = Image.open(dest)
    except Exception:
        return None
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width > TARGET_W:
        h = max(1, round(im.height * TARGET_W / im.width))
        im = im.resize((TARGET_W, h), Image.LANCZOS)
    q = QUALITY
    while True:
        im.save(dest, "JPEG", quality=q, optimize=True, progressive=True)
        sz = os.path.getsize(dest)
        if sz <= MAX_BYTES or q <= 55:
            break
        q -= 7
    return im.width, im.height, os.path.getsize(dest)


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main():
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

    os.makedirs(OUTDIR, exist_ok=True)
    skel = json.load(open(SKELETON, encoding="utf-8"))
    nodes = skel["nodes"]

    manifest = {}
    if os.path.exists(MANIFEST) and not force:
        try:
            manifest = json.load(open(MANIFEST, encoding="utf-8"))
        except Exception:
            manifest = {}
    missing = manifest.get("_missing", {}) if not force else {}
    manifest.pop("_missing", None)

    order = sorted(nodes, key=lambda n: (n["tradition"] != "west",))
    total = len(order)

    for i, node in enumerate(order, 1):
        nid = node["id"]
        if only and nid not in only:
            continue
        dest = os.path.join(OUTDIR, f"{nid}.jpg")
        if (not force) and os.path.exists(dest) and nid in manifest:
            continue

        name_en = node["nameEn"]
        w0 = node["works"][0]
        toks = artist_tokens(name_en)
        title_toks = [t for t in norm(w0.get("titleEn", "")).split() if len(t) > 3]
        queries = build_queries(node)

        pool, seen_t = [], set()

        def add_all(cands, need_artist=False):
            for c in cands:
                ok, _ = basic_filters(c)
                if not ok or c["title"] in seen_t:
                    continue
                if need_artist and not any(
                        t in norm(c["title"].replace("File:", "")) for t in toks):
                    continue
                seen_t.add(c["title"])
                pool.append(c)

        for qi, q in enumerate(queries[:5]):
            add_all(commons_search(q, limit=12))
            time.sleep(0.7)
            if len(pool) >= 8 and qi >= 1:
                break

        if not pool:
            # 退一步：intitle 精确搜文件名
            for q in queries[:3]:
                if len(q.split()) >= 2 or re.search(r"[\u4e00-\u9fff]", q):
                    add_all(commons_search(f'intitle:"{q}"', limit=12))
                    time.sleep(0.7)
                    if pool:
                        break

        if not pool:
            # 再退一步：搜画家本人，要求文件名命中画家 token
            add_all(commons_search(name_en, limit=20), need_artist=True)
            time.sleep(0.7)

        if not pool:
            missing[nid] = "Commons 无符合授权/尺寸的候选"
            print(f"[{i}/{total}] MISS  {nid:16s} ({w0['title']})")
            continue

        best = pick(pool, toks, title_toks, prefer_partial=False)
        ar = best["w"] / max(best["h"], 1)
        partial = is_partial_name(best["title"].replace("File:", ""))
        if ar > 8.0:
            alt = pick(pool, toks, title_toks, prefer_partial=True)
            if alt is not None and (alt["w"] / max(alt["h"], 1)) <= 4.5:
                best, partial = alt, True

        fname = best["title"].replace("File:", "")
        meta = best["meta"]
        lic = meta_val(meta, "LicenseShortName")
        credit = meta_val(meta, "Credit") or meta_val(meta, "Artist") or "Wikimedia Commons"
        obj = meta_val(meta, "ObjectName") or fname.rsplit(".", 1)[0]

        if dry:
            print(f"[{i}/{total}] DRY   {nid:16s} -> {fname[:70]} "
                  f"[{lic}] {best['w']}x{best['h']}")
            continue

        ok, url = download(best["title"], dest)
        if not ok:
            missing[nid] = "下载失败（FilePath 返回异常）"
            print(f"[{i}/{total}] FAIL  {nid:16s} 下载失败")
            continue
        dim = compress(dest)
        if not dim:
            missing[nid] = "文件损坏/非图片"
            if os.path.exists(dest):
                os.remove(dest)
            print(f"[{i}/{total}] FAIL  {nid:16s} 非图片")
            continue

        w, h, sz = dim
        enc = urllib.parse.quote(fname.replace(" ", "_"), safe="")
        manifest[nid] = {
            "file": f"assets/works/{nid}.jpg",
            "commonsFile": best["title"],
            "commonsPage": "https://commons.wikimedia.org/wiki/" +
                           urllib.parse.quote(best["title"].replace(" ", "_"), safe=":/"),
            "license": lic,
            "credit": credit[:200],
            "objectName": obj[:200],
            "w": w, "h": h,
            "partial": bool(partial or ar > 8),
            "remote": f"{FILEPATH}{enc}?width={TARGET_W}",
        }
        missing.pop(nid, None)
        print(f"[{i}/{total}] OK    {nid:16s} -> {fname[:60]} "
              f"[{lic}] {w}x{h} {sz//1024}KB{' [局部]' if partial else ''}")
        time.sleep(0.25)

    if not dry:
        manifest["_missing"] = missing
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        got = len([k for k in manifest if not k.startswith("_")])
        tot = 0
        for fn in os.listdir(OUTDIR):
            p = os.path.join(OUTDIR, fn)
            if os.path.isfile(p):
                tot += os.path.getsize(p)
        print(f"\n=== 完成 {got}/{total}  缺 {len(missing)}  总容量 {tot/1024/1024:.2f}MB ===")
        if missing:
            for k, v in missing.items():
                print(f"  missing: {k} — {v}")


if __name__ == "__main__":
    main()
