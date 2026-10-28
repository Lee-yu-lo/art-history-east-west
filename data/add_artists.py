#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把三件事合进主数据：
  1) 新增画家（节点 + 关系边）
  2) copy_add.json 里的新增文案
  3) corrections.json 里 confidence=high 的史料修正

幂等：重复运行不会产生重复节点/边。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------- 1. 新增画家 ----------
NEW_NODES = [
    dict(id="guan_tong", name="关仝", nameEn="Guan Tong", tradition="china", born=907, died=960,
         era="c_five", school="五代北方山水", region="五代·长安", uncertain=True,
         works=[dict(title="关山行旅图", titleEn="Guan Tong Traveling in the Mountains",
                     year="约10世纪", sortYear=950)]),
    dict(id="liu_songnian", name="刘松年", nameEn="Liu Songnian", tradition="china", born=1155, died=1218,
         era="c_song", school="南宋院体", region="南宋·钱塘", uncertain=True,
         works=[dict(title="四景山水图", titleEn="Liu Songnian Four Views of Landscape",
                     year="约1190", sortYear=1190)]),
    dict(id="wu_zhen", name="吴镇", nameEn="Wu Zhen", tradition="china", born=1280, died=1354,
         era="c_yuan", school="元四家", region="元·嘉兴", uncertain=False,
         works=[dict(title="渔父图", titleEn="Wu Zhen Fisherman", year="约1340", sortYear=1340)]),
    dict(id="wang_meng", name="王蒙", nameEn="Wang Meng (Yuan painter)", tradition="china", born=1308, died=1385,
         era="c_yuan", school="元四家", region="元·吴兴", uncertain=False,
         works=[dict(title="青卞隐居图", titleEn="Wang Meng Dwelling in the Qingbian Mountains",
                     year="1366", sortYear=1366)]),
    dict(id="kun_can", name="髡残", nameEn="Kuncan", tradition="china", born=1612, died=1673,
         era="c_qing", school="清四僧", region="明末清初·南京", uncertain=False,
         works=[dict(title="层岩叠壑图", titleEn="Kuncan Layered Rocks and Ravines",
                     year="约1660", sortYear=1660)]),
    dict(id="hongren", name="弘仁", nameEn="Hongren (painter)", tradition="china", born=1610, died=1664,
         era="c_qing", school="清四僧·新安画派", region="清·安徽歙县", uncertain=True,
         works=[dict(title="黄海松石图", titleEn="Hongren Pines and Rocks of the Yellow Sea",
                     year="约1660", sortYear=1660)]),
    dict(id="lin_fengmian", name="林风眠", nameEn="Lin Fengmian", tradition="china", born=1900, died=1991,
         era="c_modern", school="中西融合", region="近现代·上海", uncertain=False,
         works=[dict(title="鹭", titleEn="Lin Fengmian Egrets", year="约1960", sortYear=1960)]),
    dict(id="velazquez", name="委拉斯开兹", nameEn="Diego Velázquez", tradition="west", born=1599, died=1660,
         era="w_baroque", school="巴洛克·西班牙宫廷", region="西班牙", uncertain=False,
         works=[dict(title="宫娥", titleEn="Las Meninas Velazquez", year="1656", sortYear=1656)]),
    dict(id="goya", name="戈雅", nameEn="Francisco Goya", tradition="west", born=1746, died=1828,
         era="w_romanticism", school="浪漫主义先声", region="西班牙", uncertain=False,
         works=[dict(title="1808年5月3日", titleEn="The Third of May 1808 Goya", year="1814", sortYear=1814)]),
    dict(id="malevich", name="马列维奇", nameEn="Kazimir Malevich", tradition="west", born=1879, died=1935,
         era="w_modernism", school="至上主义·几何抽象", region="俄国", uncertain=False,
         works=[dict(title="黑方块", titleEn="Black Square Malevich", year="1915", sortYear=1915)]),
]

NEW_EDGES = [
    dict(source="jing_hao", target="guan_tong", type="lineage", label="荆关并称，北方石山"),
    dict(source="guan_tong", target="li_cheng", type="influence", label="李成师法荆关"),
    dict(source="li_tang", target="liu_songnian", type="lineage", label="南宋四家"),
    dict(source="liu_songnian", target="ma_yuan", type="milieu", label="南宋院体同代"),
    dict(source="huang_gongwang", target="wu_zhen", type="milieu", label="元四家"),
    dict(source="wu_zhen", target="ni_zan", type="milieu", label="元四家"),
    dict(source="zhao_mengfu", target="wang_meng", type="lineage", label="外祖父赵孟頫"),
    dict(source="ni_zan", target="wang_meng", type="milieu", label="元四家"),
    dict(source="bada_shanren", target="kun_can", type="milieu", label="清四僧"),
    dict(source="kun_can", target="shi_tao", type="milieu", label="清四僧"),
    dict(source="bada_shanren", target="hongren", type="milieu", label="清四僧"),
    dict(source="hongren", target="kun_can", type="milieu", label="清四僧"),
    dict(source="hongren", target="shi_tao", type="milieu", label="清四僧"),
    dict(source="xu_beihong", target="lin_fengmian", type="milieu", label="同代中西融合的不同路"),
    dict(source="caravaggio", target="velazquez", type="influence", label="明暗对照传到西班牙"),
    dict(source="velazquez", target="goya", type="influence", label="宫廷写实传统的延续"),
    dict(source="velazquez", target="rembrandt", type="milieu", label="同期宫廷与市民的两条路"),
    dict(source="goya", target="delacroix", type="influence", label="浪漫主义的先声"),
    dict(source="kandinsky", target="malevich", type="milieu", label="抽象的两条路"),
    dict(source="malevich", target="mondrian", type="influence", label="几何抽象的推进"),
]

# 生卒年/归属存疑的补充标注
FLAG_UNCERTAIN = ["guan_tong", "liu_songnian", "kun_can", "wu_zhen"]


def add_artists(skel, copy):
    ids = {n["id"] for n in skel["nodes"]}
    added = 0
    for n in NEW_NODES:
        if n["id"] in ids:
            continue
        skel["nodes"].append(n)
        ids.add(n["id"])
        added += 1
    ekeys = {(e["source"], e["target"], e["type"]) for e in skel["edges"]}
    added_e = 0
    for e in NEW_EDGES:
        k = (e["source"], e["target"], e["type"])
        if k in ekeys or e["source"] not in ids or e["target"] not in ids:
            continue
        skel["edges"].append(e)
        ekeys.add(k)
        added_e += 1

    # 合并 copy_add.json
    add = load(os.path.join(DATA, "copy_add.json"), {})
    cn = copy.setdefault("nodes", {})
    cw = copy.setdefault("works", {})
    for k, v in (add.get("nodes") or {}).items():
        cn.setdefault(k, v)
    for k, v in (add.get("works") or {}).items():
        cw.setdefault(k, v)
    daily = copy.setdefault("daily", [])
    have = {d["id"] for d in daily}
    for d in (add.get("daily") or []):
        if d.get("id") and d["id"] not in have:
            daily.append(d)
            have.add(d["id"])
    return added, added_e, len(add.get("daily") or [])


# ---------- 2. 应用史料修正 ----------
def apply_corrections(skel, corr):
    items = corr.get("corrections") or []
    byid = {n["id"]: n for n in skel["nodes"]}
    applied, skipped = [], []
    for c in items:
        if c.get("confidence") != "high":
            skipped.append((c.get("id"), c.get("field"), "非 high 置信度"))
            continue
        n = byid.get(c.get("id"))
        f = c.get("field")
        if not n or not f:
            skipped.append((c.get("id"), f, "找不到条目/字段"))
            continue
        # 代表作字段在 works[0] 里
        if f in ("title", "wyear", "sortYear", "work"):
            w = (n.get("works") or [{}])[0]
            key = {"wyear": "year", "work": "title"}.get(f, f)
            if w.get(key) == c.get("new"):
                continue
            w[key] = c.get("new")
        else:
            if n.get(f) == c.get("new"):
                continue
            n[f] = c.get("new")
        applied.append((c["id"], f, str(c.get("old"))[:22], str(c.get("new"))[:22]))
    # 存疑标注
    flags = []
    for f in (corr.get("flagUncertain") or []):
        n = byid.get(f.get("id"))
        if n and not n.get("uncertain"):
            n["uncertain"] = True
            flags.append(f["id"])
    for i in FLAG_UNCERTAIN:
        n = byid.get(i)
        if n and not n.get("uncertain"):
            n["uncertain"] = True
    # 活动期 / 推定生卒的具体说明，给用户看得懂的限定语
    notes = []
    for d in (corr.get("dateNotes") or []):
        n = byid.get(d.get("id"))
        if n and n.get("dateNote") != d.get("note"):
            n["dateNote"] = d.get("note")
            notes.append(d["id"])
    return applied, skipped, flags, notes


def apply_edge_fixes(skel, corr):
    """改写不成立的关系边 type/label，并删除应删的边。"""
    fixed, removed, miss = [], [], []
    for ef in (corr.get("edgeFixes") or []):
        if ef.get("confidence") != "high":
            continue
        hit = False
        for e in skel["edges"]:
            if e["source"] == ef.get("source") and e["target"] == ef.get("target"):
                old = (e.get("type"), e.get("label"))
                e["type"] = ef.get("type", e["type"])
                e["label"] = ef.get("label", e["label"])
                fixed.append((ef["source"], ef["target"], "%s/%s" % old, "%s/%s" % (e["type"], e["label"])))
                hit = True
        if not hit:
            miss.append((ef.get("source"), ef.get("target"), ef.get("label")))
    keep = []
    rkeys = {(r.get("source"), r.get("target")) for r in (corr.get("removeEdges") or [])}
    for e in skel["edges"]:
        if (e["source"], e["target"]) in rkeys:
            removed.append((e["source"], e["target"]))
        else:
            keep.append(e)
    skel["edges"] = keep
    return fixed, removed, miss


def apply_copy_fixes(copy, corr):
    """对 copy.json 的正文做定点替换，old 必须逐字命中才算成功。"""
    cn = copy.setdefault("nodes", {})
    done, miss = [], []
    for c in (corr.get("copyFixes") or []):
        if c.get("confidence") != "high":
            continue
        ent = cn.get(c.get("id"))
        if not ent or c.get("field") not in ent:
            miss.append((c.get("id"), c.get("field")))
            continue
        cur = ent[c["field"]]
        if c["old"] not in cur:
            miss.append((c.get("id"), c.get("field"), "原文未命中"))
            continue
        ent[c["field"]] = cur.replace(c["old"], c["new"])
        done.append((c["id"], c["field"]))
    return done, miss


def chronology_sanity(skel):
    """边类型与年代是否自洽：milieu/rival/lineage 要求两人有生卒重叠。"""
    byid = {n["id"]: n for n in skel["nodes"]}
    bad = []
    for e in skel["edges"]:
        a, b = byid.get(e["source"]), byid.get(e["target"])
        if not a or not b:
            continue
        if e["type"] not in ("milieu", "rival", "lineage"):
            continue
        lo = max(a.get("born") or -9999, b.get("born") or -9999)
        hi = min(a.get("died") or 9999, b.get("died") or 9999)
        if lo > hi:
            bad.append((e["source"], e["target"], e["type"], "%s–%s / %s–%s" % (
                a.get("born"), a.get("died"), b.get("born"), b.get("died"))))
    return bad


def validate(skel):
    ids = {n["id"] for n in skel["nodes"]}
    bad = [e for e in skel["edges"] if e["source"] not in ids or e["target"] not in ids]
    linked = {x for e in skel["edges"] for x in (e["source"], e["target"])}
    iso = sorted(ids - linked)
    eraids = {e["id"] for e in skel["eras"]["china"]} | {e["id"] for e in skel["eras"]["west"]}
    bade = sorted({n["era"] for n in skel["nodes"]} - eraids)
    return bad, iso, bade


def main():
    skel = load(os.path.join(DATA, "skeleton.json"), {})
    copy = load(os.path.join(DATA, "copy.json"), {})

    a_n, a_e, a_d = add_artists(skel, copy)
    print("新增画家 %d · 新增关系 %d · 新增每日一画 %d" % (a_n, a_e, a_d))

    cpath = os.path.join(DATA, "corrections.json")
    if os.path.exists(cpath):
        corr = load(cpath, {})
        applied, skipped, flags, notes = apply_corrections(skel, corr)
        print("史料修正采纳 %d 条，跳过 %d 条" % (len(applied), len(skipped)))
        for x in applied:
            print("   %-16s %-10s %s → %s" % x)
        for x in skipped:
            print("   跳过 %s.%s（%s）" % x)
        if flags:
            print("   补标存疑:", ", ".join(flags))
        if notes:
            print("   年代限定语:", ", ".join(notes))

        fixed, removed, miss = apply_edge_fixes(skel, corr)
        print("关系边改写 %d 条，删除 %d 条" % (len(fixed), len(removed)))
        for x in fixed:
            print("   %-14s → %-14s %s  ⇒  %s" % x)
        for x in removed:
            print("   删除 %s → %s" % x)
        if miss:
            print("   未命中的边修正:", miss)

        cdone, cmiss = apply_copy_fixes(copy, corr)
        print("正文校正 %d 处，未命中 %d 处" % (len(cdone), len(cmiss)))
        for x in cmiss:
            print("   未命中", x)
    else:
        print("（无 corrections.json，跳过修正）")

    chron = chronology_sanity(skel)
    if chron:
        print("⚠ 年代不自洽的边 %d 条：" % len(chron))
        for x in chron:
            print("   %s → %s [%s] %s" % x)
    else:
        print("年代自洽性检查：通过")

    bad, iso, bade = validate(skel)
    print("悬空边 %d · 孤立节点 %s · 未知分期 %s" % (len(bad), iso or "无", bade or "无"))

    save(os.path.join(DATA, "skeleton.json"), skel)
    save(os.path.join(DATA, "copy.json"), copy)
    print("已写回 skeleton.json / copy.json")
    print("节点 %d（中 %d / 西 %d）· 边 %d" % (
        len(skel["nodes"]),
        sum(1 for n in skel["nodes"] if n["tradition"] == "china"),
        sum(1 for n in skel["nodes"] if n["tradition"] == "west"),
        len(skel["edges"])))


if __name__ == "__main__":
    main()
