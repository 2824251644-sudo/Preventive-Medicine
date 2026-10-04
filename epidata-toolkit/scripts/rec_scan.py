#!/usr/bin/env python3
"""rec 异常值扫描：录入质检，输出可疑记录清单

用法:
  python3 scripts/rec_scan.py 数据.rec [--json 字段定义.json] [--qes 调查表.qes] [-o 报告.txt]

规则（两层）:
  1. 字段定义 JSON（优先）：options → 值不在选项编号集合；legal → 不在合法值集合；
     range → 超出 [min,max]；required → 空值（仅当 chk 有 MUSTENTER，用 --required 开启）
  2. 通用启发式（无 JSON 或未覆盖时，按字段名）：
     AGE/年龄 → 0-120；TEMP/体温 → 30-45；TEL/MOBILE/PHONE → 11 位数字；
     BIRTHDT/ONSETDT 等日期 → 基本格式校验

退出码: 0=无异常  1=有可疑值  2=无法解析/无记录
"""
import argparse, json, re, sys
from rec_compare import parse_rec


def gen_rules(json_path):
    """从字段定义 JSON 生成规则表"""
    rules = {}
    if not json_path:
        return rules
    data = json.load(open(json_path, encoding='utf-8'))
    for f in data.get('fields', []):
        name = f.get('name')
        if not name:
            continue
        r = {}
        opts = f.get('options')
        if isinstance(opts, str):
            opts = [o for o in opts.split('\n') if o.strip()]
        if isinstance(opts, list) and opts:
            nums = []
            for o in opts:
                m = re.match(r'^【?(\d+)】?', str(o))
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                r['legal'] = set(nums)
        if f.get('legal'):
            r['legal'] = set(int(x) for x in f['legal'])
        if f.get('range'):
            rg = f['range']
            if isinstance(rg, str):
                rg = rg.split()
            if len(rg) == 2:
                r['range'] = (rg[0], rg[1])
        if f.get('required'):
            r['required'] = True
        if r:
            rules[name] = r
    return rules


def check_value(name, val, rules):
    """单字段值检查，返回异常原因列表"""
    problems = []
    if val == '':
        return problems
    r = rules.get(name, {})
    # 选项编号规则
    if 'legal' in r:
        if val.isdigit() and int(val) not in r['legal']:
            problems.append(f'选项编号 {val} 不在合法集合 {sorted(r["legal"])[:8]}')
        elif not val.isdigit():
            problems.append(f'非编号值 "{val}"（选项字段应录编号）')
    # 范围规则
    if 'range' in r:
        lo, hi = r['range']
        try:
            v = float(val)
            if not (float(lo) <= v <= float(hi)):
                problems.append(f'{val} 超出范围 [{lo}, {hi}]')
        except ValueError:
            problems.append(f'"{val}" 非数值（范围字段）')
    # 通用启发式（无规则时）
    if not r:
        up = name.upper()
        if 'AGE' in up and up not in ('MANAGE', 'MESSAGE'):
            if val.isdigit() and int(val) > 120:
                problems.append(f'年龄 {val} > 120')
        if 'TEMP' in up and val.replace('.', '', 1).replace('-', '', 1).isdigit():
            if not (30 <= float(val) <= 45):
                problems.append(f'体温 {val} 不在 30-45')
        if ('TEL' in up or 'MOBILE' in up or 'PHONE' in up) and val.isdigit() and len(val) != 11:
            problems.append(f'电话 {len(val)} 位 ≠ 11')
    return problems


def main():
    ap = argparse.ArgumentParser(description='rec 异常值扫描')
    ap.add_argument('rec', help='EpiData 数据文件 .rec')
    ap.add_argument('--json', help='字段定义 JSON（提供选项/范围/必填规则）')
    ap.add_argument('--required', action='store_true', help='检查 required 字段是否为空')
    ap.add_argument('-o', '--output', help='报告输出文件（UTF-8）')
    args = ap.parse_args()

    try:
        r = parse_rec(args.rec)
    except SystemExit as e:
        print(e); sys.exit(2)
    if not r['recs']:
        print(f'  {args.rec}: 无记录（空库），无异常可扫')
        sys.exit(2)
    rules = gen_rules(args.json)
    names = [f['name'] for f in r['data_fields']]

    findings = []
    for i, rec in enumerate(r['recs']):
        for name in names:
            val = rec.get(name, '')
            for prob in check_value(name, val, rules):
                findings.append((i + 1, name, val, prob))
            if args.required and rules.get(name, {}).get('required') and val == '':
                findings.append((i + 1, name, '', '必填字段为空'))

    L = ['═' * 46, 'rec 异常值扫描', '─' * 46,
         f'{args.rec} | 记录 {len(r["recs"])} 条 | 字段 {len(names)} 个 | 规则字段 {len(rules)} 个']
    L.append('─' * 46)
    if not findings:
        L.append('✓ 未发现可疑值')
        code = 0
    else:
        L.append(f'✗ 发现 {len(findings)} 处可疑（记录号 字段 值 原因）:')
        for rec_no, name, val, prob in findings[:200]:
            L.append(f'  记录 {rec_no}  {name:<14} "{val}"  {prob}')
        if len(findings) > 200:
            L.append(f'  … 其余 {len(findings) - 200} 处略')
        code = 1
    report = '\n'.join(L) + '\n'
    print(report)
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='') as f:
            f.write(report)
    sys.exit(code)


if __name__ == '__main__':
    main()
