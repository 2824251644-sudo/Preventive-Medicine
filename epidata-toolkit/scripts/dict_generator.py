#!/usr/bin/env python3
"""字段字典 + 录入员手册生成（写论文方法学 / 数据字典 / 录入培训用）

用法:
  python3 scripts/dict_generator.py 字段定义.json -o 输出基础名 [--qes 调查表.qes] [--csv]

输出（同基础名）:
  <名>_数据字典.md   变量名 ↔ 中文标签 ↔ 类型/掩码 ↔ 选项 ↔ 规则 对照表
  <名>_录入手册.md   给录入员的逐字段填写说明（按章节）
  <名>_数据字典.csv  纯表（SPSS 变量视图导入用，--csv 才生成）

说明:
  - 章节按字段 label 顺序自动分段（遇到"一、二、三、"或"1. 2."式标题文本切章）
  - label 优先取 --qes 的 {字段} 文本（更接近问卷原文）
"""
import argparse, json, re, sys
from rec_export import extract_labels


def mask_desc(f):
    ftype = f.get('type', 'text')
    if ftype == 'number':
        return f"数字（digits={f.get('digits', '自动')}）"
    if ftype == 'date':
        return f"日期（{f.get('date_format', '<dd/mm/yyyy>')}）"
    if ftype == 'time':
        return '时间（##时##分）'
    if ftype == 'memo':
        return f"长文本（{f.get('length', '?')}字）"
    return f"文本（{f.get('length', '?')}字）"


def rule_desc(f):
    parts = []
    if f.get('required'):
        parts.append('必填')
    if f.get('range'):
        rg = f['range']
        parts.append(f"范围 {rg if isinstance(rg, str) else ' '.join(map(str, rg))}")
    if f.get('legal'):
        parts.append(f"限值 {f['legal']}")
    if f.get('jumps'):
        js = ', '.join(f"{k}→{v}" for k, v in f['jumps'].items())
        parts.append(f"跳转 {js}")
    return '；'.join(parts) or '—'


def options_list(f):
    opts = f.get('options')
    if isinstance(opts, str):
        opts = [o for o in opts.split('\n') if o.strip()]
    return opts or []


def fill_guide(f):
    """录入手册：每个字段怎么填"""
    ftype = f.get('type', 'text')
    label = f.get('label', '')
    if ftype == 'date':
        return f'按 {f.get("date_format", "<dd/mm/yyyy>")} 格式填写（日/月/年），自动日期无需手输。'
    if ftype == 'time':
        return '填 ##时##分（如 08:30 录 8 时 30 分）。'
    opts = options_list(f)
    if opts:
        has_other = any('其他' in str(o) or '其它' in str(o) for o in opts)
        tip = '选其他时须在注明栏填写具体内容。' if has_other else ''
        return f'录选项编号（如 1/2/3）。{tip}'
    if ftype == 'number':
        if '电话' in label or '手机' in label:
            return '录 11 位手机号，勿加空格或横线。'
        return '录数字。'
    return '照实填写文本。'


def split_sections(fields, labels):
    """按章节标题文本切段"""
    sections = []
    cur_title, cur = '（未分节）', []
    for f in fields:
        lab = labels.get(f.get('name'), f.get('label', ''))
        if re.match(r'^[一二三四五六七八九十]+、', lab.strip()):
            if cur:
                sections.append((cur_title, cur))
            cur_title = lab.strip()[:20]
            cur = []
        cur.append((f, lab))
    if cur:
        sections.append((cur_title, cur))
    return sections


def main():
    ap = argparse.ArgumentParser(description='字段字典 + 录入手册生成')
    ap.add_argument('json', help='字段定义 JSON')
    ap.add_argument('-o', '--output', required=True, help='输出基础名（不含扩展名）')
    ap.add_argument('--qes', help='调查表 .qes（提取中文标签，更贴近原文）')
    ap.add_argument('--csv', action='store_true', help='额外生成 CSV 对照表')
    args = ap.parse_args()

    data = json.load(open(args.json, encoding='utf-8'))
    fields = data.get('fields', [])
    labels = extract_labels(args.qes) if args.qes else {}
    title = data.get('title', args.json)

    # 数据字典
    L = [f'# {title} 数据字典', '',
         f'字段总数：{len(fields)} | 生成：EpiData Toolkit', '',
         '| 字段名 | 中文标签 | 类型/掩码 | 选项 | 规则 |',
         '|---|---|---|---|---|']
    for f in fields:
        name = f.get('name', '?')
        lab = labels.get(name) or f.get('label', '')
        opts = options_list(f)
        opt_txt = '、'.join(str(o).replace('\n', '') for o in opts[:6])
        if len(opts) > 6:
            opt_txt += f' 等{len(opts)}项'
        L.append(f"| {name} | {lab} | {mask_desc(f)} | {opt_txt or '—'} | {rule_desc(f)} |")
    with open(args.output + '_数据字典.md', 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(L) + '\n')
    print(f'✓ 数据字典: {args.output}_数据字典.md（{len(fields)} 字段）')

    # 录入手册
    M = [f'# {title} 录入手册', '',
         '填表原则：选项字段录编号；日期按格式；"其他"须注明；带 * 的为必填。', '']
    for sec_title, items in split_sections(fields, labels):
        M.append(f'## {sec_title}')
        for f, lab in items:
            req = '（必填）' if f.get('required') else ''
            M.append(f'- **{f.get("name")}**{req} {lab}：{fill_guide(f)}')
        M.append('')
    with open(args.output + '_录入手册.md', 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(M) + '\n')
    print(f'✓ 录入手册: {args.output}_录入手册.md')

    # CSV
    if args.csv:
        import csv as csv_mod
        with open(args.output + '_数据字典.csv', 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv_mod.writer(fh)
            w.writerow(['字段名', '中文标签', '类型', '掩码', '选项', '规则'])
            for f in fields:
                name = f.get('name', '?')
                w.writerow([name, labels.get(name) or f.get('label', ''), f.get('type', ''),
                            mask_desc(f), '；'.join(map(str, options_list(f))), rule_desc(f)])
        print(f'✓ 数据字典 CSV: {args.output}_数据字典.csv')


if __name__ == '__main__':
    main()
