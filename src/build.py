#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 skeleton + copy + 图片 manifest 合成单文件 index.html"""
import json, os, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
DATA_DIR = os.path.join(ROOT, 'data')
ASSETS = os.path.join(ROOT, 'assets', 'works')

def load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime('%m%d')
    skel = load(os.path.join(DATA_DIR, 'skeleton.json'), {})
    copy = load(os.path.join(DATA_DIR, 'copy.json'), {})
    man  = load(os.path.join(ASSETS, 'manifest.json'), {})

    images = {}
    missing = man.pop('_missing', {}) if isinstance(man, dict) else {}
    for k, v in man.items():
        if k.startswith('_'):
            continue
        images[k] = v

    site = copy.get('site', {})
    data = {
        'meta': {'version': ver, 'built': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                 'nodes': len(skel.get('nodes', [])), 'edges': len(skel.get('edges', [])),
                 'images': len(images), 'missing': len(missing)},
        'site': site,
        'eras': skel.get('eras', {'china': [], 'west': []}),
        'nodes': skel.get('nodes', []),
        'edges': skel.get('edges', []),
        'essays': copy.get('essays', []),
        'daily': copy.get('daily', []),
        'terms': copy.get('terms', []),
        'images': images,
        'copy': {
            'nodes': copy.get('nodes', {}),
            'works': copy.get('works', {}),
            'eras': copy.get('eras', {}),
        },
    }

    tpl = open(os.path.join(SRC, 'template.html'), encoding='utf-8').read()
    app = open(os.path.join(SRC, 'app.js'), encoding='utf-8').read()

    title = site.get('title', '中西方美术史')
    desc = site.get('subtitle', '画家关系图、名作时间轴与入门导读')
    lead = site.get('heroLead', '')
    note = site.get('heroNote', '')

    tpl = (tpl.replace('__TITLE__', title)
              .replace('__DESC__', desc)
              .replace('__LEAD__', lead)
              .replace('__NOTE__', note)
              .replace('__VER__', ver)
              .replace('__BUILD__', data['meta']['built']))
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('</script>', '<\\/script>')
    out = tpl.replace('/*__DATA__*/null', payload).replace('/*__APP__*/', app)

    dst = os.path.join(ROOT, 'index.html')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(out)

    size = os.path.getsize(dst)
    print('built ->', dst)
    print('  nodes=%d edges=%d essays=%d terms=%d daily=%d images=%d missing=%d' % (
        len(data['nodes']), len(data['edges']), len(data['essays']),
        len(data['terms']), len(data['daily']), len(images), len(missing)))
    print('  index.html %.1f KB' % (size / 1024.0))
    if missing:
        print('  missing:', ', '.join(list(missing)[:20]))

if __name__ == '__main__':
    main()
