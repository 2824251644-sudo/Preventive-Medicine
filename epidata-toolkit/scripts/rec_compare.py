#!/usr/bin/env python3
"""rec 双录入比对工具（EpiData rec 文本格式原生解析，自包含，无需字段 JSON）

用法:
  python3 scripts/rec_compare.py 录入1.rec 录入2.rec [-o 差异报告.txt]

EpiData .rec 真实格式（已实测校准，肺结核/禽流感标准格式验证）:
  1. 首行:   <字段数> <记录数> Filelabel: <标签长度>
  2. 字段定义区: 每行一个字段
     _字段名<填充> <记录号> <序号> 30 <标签字节长> <序号> <类型码> <宽度> 112 <字段名><标签文本>
     类型码: 0=LABEL/标题(宽0)  1=文本(宽=字数x2)  6=数字(宽=位数)
             11=日期(宽10)      101=小数(宽=位数+小数位+2)
  3. 数据区: 字段定义区之后的定长字节流
     每条记录宽度 = 全部非 LABEL 字段宽度之和，字段按定义顺序排列

比对逻辑:
  先比对两个 rec 的字段定义（字段数/名称/宽度），不一致时报警；
  再按记录号逐字段比对数据（数字/文本统一去首尾空白）。
"""
import argparse, re, sys

FIELD_PAT = re.compile(
    r'^\s*([#_]?)([A-Za-z][A-Za-z0-9]*)\s+\d+\s+(\d+)\s+30\s+(\d+)\s+\d+\s+(\d+)\s+(\d+)\s+112\s+'
)

def parse_rec(path):
    """字节级解析：CRLF 定位字段定义行，字段定义区后余下字节即数据区"""
    raw = open(path, 'rb').read()
    first = raw.find(b'\r\n')
    if first < 0:
        raise SystemExit(f'✗ {path}: 未找到 CRLF，非 EpiData rec 文本格式')
    head_line = raw[:first].decode('gbk', errors='replace').strip()
    head = head_line.split()
    if len(head) < 2:
        raise SystemExit(f'✗ {path}: 首行格式异常: {head_line!r}')
    n_fields, n_recs = int(head[0]), int(head[1])
    fields = []
    pos = first + 2  # 跳过首行 CRLF
    for _ in range(n_fields):
        eol = raw.find(b'\r\n', pos)
        if eol < 0:
            raise SystemExit(f'✗ {path}: 字段定义区在第 {len(fields)} 个字段后提前结束')
        ln = raw[pos:eol].decode('gbk', errors='replace')
        m = FIELD_PAT.match(ln)
        if not m:
            raise SystemExit(f'✗ {path}: 字段定义行无法解析: {ln[:80]!r}')
        fields.append({'name': m.group(2), 'seq': int(m.group(3)),
                       'typ': int(m.group(5)), 'width': int(m.group(6))})
        pos = eol + 2
    data = raw[pos:]
    data_fields = [f for f in fields if f['width'] > 0]
    rec_w = sum(f['width'] for f in data_fields)
    n = min(n_recs, len(data) // rec_w) if rec_w else 0
    if rec_w and len(data) % rec_w:
        print(f'  ⚠ {path}: 数据区 {len(data)} 字节非记录宽 {rec_w} 整数倍，尾部 {len(data) % rec_w} 字节忽略')
    recs = []
    for i in range(n):
        chunk = data[i * rec_w:(i + 1) * rec_w]
        off, rec = 0, {}
        for f in data_fields:
            v = chunk[off:off + f['width']].decode('gbk', errors='replace').strip()
            rec[f['name']] = v
            off += f['width']
        recs.append(rec)
    return {'path': path, 'n_fields': n_fields, 'n_recs': n_recs,
            'fields': fields, 'data_fields': data_fields, 'rec_w': rec_w,
            'data_len': len(data), 'recs': recs}

def main():
    ap = argparse.ArgumentParser(description='rec 双录入比对（EpiData 文本格式原生解析）')
    ap.add_argument('rec1', help='录入1 .rec 文件')
    ap.add_argument('rec2', help='录入2 .rec 文件')
    ap.add_argument('-o', '--output', help='差异报告输出文件（UTF-8）')
    args = ap.parse_args()

    r1, r2 = parse_rec(args.rec1), parse_rec(args.rec2)
    L = ['═' * 46, 'rec 双录入比对报告', '─' * 46]
    L.append(f'录入1 : {r1["path"]}')
    L.append(f'       字段 {r1["n_fields"]} 个 | 记录声明 {r1["n_recs"]} | 数据区 {r1["data_len"]} 字节 | 实际记录 {len(r1["recs"])} 条')
    L.append(f'录入2 : {r2["path"]}')
    L.append(f'       字段 {r2["n_fields"]} 个 | 记录声明 {r2["n_recs"]} | 数据区 {r2["data_len"]} 字节 | 实际记录 {len(r2["recs"])} 条')
    L.append('─' * 46)

    # 1) 字段定义一致性
    s1 = [(f['name'], f['width']) for f in r1['data_fields']]
    s2 = [(f['name'], f['width']) for f in r2['data_fields']]
    if s1 != s2:
        L.append('⚠ 字段定义不一致（名称/顺序/宽度）——两 rec 非同源，无法逐字段比对')
        nm1 = {f['name'] for f in r1['data_fields']}
        nm2 = {f['name'] for f in r2['data_fields']}
        only1, only2 = nm1 - nm2, nm2 - nm1
        if only1:
            L.append(f'  仅录入1有: {sorted(only1)[:15]}')
        if only2:
            L.append(f'  仅录入2有: {sorted(only2)[:15]}')
        # 宽度差异
        wd = [(a, b, c) for (a, b), (c, d) in zip(s1, s2) if b != d]
        if wd:
            L.append(f'  宽度不同字段(前10): {wd[:10]}')
        report = '\n'.join(L) + '\n' + '═' * 46
        print(report)
        if args.output:
            open(args.output, 'w', encoding='utf-8', newline='\r\n').write(report + '\n')
            print(f'✓ 报告已写入 {args.output}')
        sys.exit(2)

    L.append(f'字段定义一致：{len(s1)} 个数据字段 | 记录宽度 {r1["rec_w"]} 字节')
    # 2) 数据比对
    n1, n2 = len(r1['recs']), len(r2['recs'])
    if n1 == 0 and n2 == 0:
        L.append('两文件均无录入记录（仅字段定义），比对完成')
        report = '\n'.join(L) + '\n' + '═' * 46
        print(report)
        if args.output:
            open(args.output, 'w', encoding='utf-8', newline='\r\n').write(report + '\n')
            print(f'✓ 报告已写入 {args.output}')
        return
    if n1 != n2:
        L.append(f'⚠ 记录数不一致（{n1} vs {n2}），仅比对前 min 条')
    n = min(n1, n2)
    same = diffs = diff_f = 0
    detail = []
    names = [f['name'] for f in r1['data_fields']]
    for i in range(n):
        ds = []
        for name in names:
            v1, v2 = r1['recs'][i][name], r2['recs'][i][name]
            if v1 != v2:
                ds.append((name, v1, v2))
        if ds:
            diffs += 1
            diff_f += len(ds)
            detail.append((i + 1, ds))
        else:
            same += 1
    L.append(f'一致记录 : {same}/{n} ({same / n * 100:.1f}%)' if n else '一致记录 : 0/0')
    L.append(f'差异记录 : {diffs}   差异字段 : {diff_f}')
    if detail:
        L.append('─' * 46)
        L.append('差异明细（记录号 字段: 录入1 vs 录入2）:')
        for rec_no, ds in detail[:200]:
            L.append(f'  记录 {rec_no}:')
            for name, v1, v2 in ds:
                L.append(f'    {name:<14} "{v1}" vs "{v2}"')
        if len(detail) > 200:
            L.append(f'  … 其余 {len(detail) - 200} 条差异记录略')
    report = '\n'.join(L) + '\n' + '═' * 46
    print(report)
    if args.output:
        open(args.output, 'w', encoding='utf-8', newline='\r\n').write(report + '\n')
        print(f'✓ 报告已写入 {args.output}')
    sys.exit(1 if diffs else 0)

if __name__ == '__main__':
    main()
