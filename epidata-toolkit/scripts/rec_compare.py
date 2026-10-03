#!/usr/bin/env python3
"""rec 双录入比对工具：同一调查表的两份录入逐字段比对，输出差异报告

用法:
  python3 scripts/rec_compare.py 录入1.rec 录入2.rec -f fields.json [-o 差异报告.txt]

原理:
  EpiData .rec 为定长记录文件：每条记录宽度 = 各字段掩码宽度之和，
  字段按 qes 定义顺序排列。本工具按字段定义 JSON 计算宽度并解析
  两条记录流，逐记录逐字段比对（数字/文本统一去空白比较）。

  头部处理为防御式：自动探测记录起点（选择能整除文件长度的最小偏移）。
  若你的 EpiData 版本头部结构与默认不符，可用 --skip-bytes 手动指定。

产出:
  控制台输出统计 + 差异明细；-o 指定时写入 UTF-8 报告文件。
"""
import argparse, json, os, sys

def field_width(f):
    """字段掩码宽度（与 qes_generator 掩码规则一致）"""
    t = f.get('type')
    if t == 'date':
        return 10                      # <dd/mm/yyyy>
    if t == 'time':
        return 4                       # ##时##分 = 4 位数字
    d = f.get('digits')
    if t == 'number':
        if isinstance(d, int):
            return d
        if isinstance(d, str) and '.' in d:
            a, b = d.split('.')
            return int(a) + 1 + int(b) # ##.# -> 2+1+1 = 4
        return int(d) if d is not None else 1
    # text / memo：两_=一字
    return int(f.get('length', 1)) * 2

def load_fields(path):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    fields = data.get('fields')
    if not fields:
        raise SystemExit(f'✗ {path} 缺少 fields 列表')
    return fields

def probe_skip(raw_len, rec_w, max_probe=4096):
    """探测记录起点偏移：找能整除 (len-skip) 的最小 skip（近似头部长度）"""
    for skip in range(0, min(raw_len, max_probe) + 1):
        if (raw_len - skip) % rec_w == 0:
            return skip
    return 0

def parse_rec(path, fields, rec_w, skip):
    raw = open(path, 'rb').read()
    if skip is None:
        skip = probe_skip(len(raw), rec_w)
    body = raw[skip:]
    n = len(body) // rec_w
    recs = []
    for i in range(n):
        chunk = body[i * rec_w:(i + 1) * rec_w]
        off = 0
        rec = {}
        for f in fields:
            w = field_width(f)
            val = chunk[off:off + w].decode('gbk', errors='replace').strip()
            rec[f['name']] = val
            off += w
        recs.append(rec)
    return recs, skip, n

def main():
    ap = argparse.ArgumentParser(description='rec 双录入比对（定长记录逐字段比对）')
    ap.add_argument('rec1', help='录入1 .rec 文件')
    ap.add_argument('rec2', help='录入2 .rec 文件')
    ap.add_argument('-f', '--fields', required=True, help='字段定义 JSON（与 qes/chk 同一份）')
    ap.add_argument('-o', '--output', help='差异报告输出文件（UTF-8）')
    ap.add_argument('--skip-bytes', type=int, default=None,
                    help='手动指定头部偏移（默认自动探测）')
    args = ap.parse_args()

    fields = load_fields(args.fields)
    rec_w = sum(field_width(f) for f in fields)
    widths = {f['name']: field_width(f) for f in fields}

    r1, s1, n1 = parse_rec(args.rec1, fields, rec_w, args.skip_bytes)
    r2, s2, n2 = parse_rec(args.rec2, fields, rec_w, args.skip_bytes)

    lines = []
    lines.append('═' * 46)
    lines.append('rec 双录入比对报告')
    lines.append('─' * 46)
    lines.append(f'字段定义 : {args.fields}')
    lines.append(f'字段数   : {len(fields)}    记录宽度 : {rec_w} 字节')
    lines.append(f'录入1    : {args.rec1}  ({n1} 条记录, 偏移 {s1})')
    lines.append(f'录入2    : {args.rec2}  ({n2} 条记录, 偏移 {s2})')

    if n1 != n2:
        lines.append(f'⚠ 记录数不一致（{n1} vs {n2}），仅比对前 min(n1,n2) 条')
    n = min(n1, n2)

    diffs = []
    same_rec = 0
    for i in range(n):
        rec_diffs = []
        for name in widths:
            v1, v2 = r1[i][name], r2[i][name]
            if v1 != v2:
                rec_diffs.append((name, v1, v2))
        if rec_diffs:
            diffs.append((i + 1, rec_diffs))
        else:
            same_rec += 1

    lines.append('─' * 46)
    lines.append(f'一致记录 : {same_rec}/{n} ({same_rec / n * 100:.1f}%)' if n else '一致记录 : 0/0')
    lines.append(f'差异记录 : {len(diffs)}   差异字段 : {sum(len(d) for _, d in diffs)}')
    if diffs:
        lines.append('─' * 46)
        lines.append('差异明细（记录号 字段: 录入1 vs 录入2）:')
        for rec_no, ds in diffs[:200]:
            lines.append(f'  记录 {rec_no}:')
            for name, v1, v2 in ds:
                lines.append(f'    {name:<12} "{v1}" vs "{v2}"')
        if len(diffs) > 200:
            lines.append(f'  … 其余 {len(diffs) - 200} 条差异记录略')
    lines.append('═' * 46)
    report = '\n'.join(lines)

    print(report)
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(report + '\n')
        print(f'✓ 报告已写入 {args.output}')
    sys.exit(1 if diffs else 0)

if __name__ == '__main__':
    main()
