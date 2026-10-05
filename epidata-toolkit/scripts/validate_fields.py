#!/usr/bin/env python3
"""字段定义 JSON 预校验：生成 qes/chk 前先拦下问题

用法:
  python3 scripts/validate_fields.py <fields.json> [-o 报告.txt]

检查项（ERROR 阻断 / WARN 提示）:
  1. 结构：JSON 可解析、含 fields 数组
  2. 字段名：字母开头、≤10 字符、全大写建议、唯一
  3. 类型合法：number/text/date/time/memo；label 缺失警告
  4. 选项：编号重复 / 跳号警告 / 编号位数超出显式掩码（截断风险；无 digits 自动匹配不检查）
  5. 掩码：digits 合法（"11" 或 "2.1"）、date_format 属 6 种、length 正整数
  6. 规则引用：jumps 目标字段存在、注明字段（字段名+O）存在
  7. "其他/其它"选项必须能匹配到注明字段（qes 自动补齐的除外，仅警告未配置的）

退出码: 0=通过  1=有 ERROR  2=有 WARN 无 ERROR
"""
import argparse, json, re, sys

TYPES = {'number', 'text', 'date', 'time', 'memo'}
VALID_DATES = {'<dd/mm/yyyy>', '<mm/dd/yyyy>', '<yyyy/mm/dd>',
               '<Today-dmy>', '<Today-mdy>', '<Today-ymd>'}
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9]*$')
OTHER_WORDS = ('其他', '其它')


def collect_errors_warns(data):
    errs, warns = [], []
    if not isinstance(data, dict) or 'fields' not in data:
        return ['✗ 顶层缺少 fields 数组'], []
    fields = data['fields']
    if not isinstance(fields, list) or not fields:
        return ['✗ fields 为空或非数组'], []

    names = []
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            errs.append(f'✗ fields[{i}] 不是对象'); continue
        tag = f.get('name', f'<第{i + 1}个>')
        # 字段名
        name = f.get('name', '')
        if not name:
            errs.append(f'✗ fields[{i}] 缺 name'); continue
        if not NAME_RE.match(name):
            errs.append(f'✗ {name}: 字段名必须以字母开头、仅字母数字')
        if len(name) > 10:
            errs.append(f'✗ {name}: 字段名 {len(name)} 字符 > 10（EpiData 上限）')
        names.append(name)
        # 类型
        ftype = f.get('type', 'text')
        if ftype not in TYPES:
            errs.append(f'✗ {name}: 非法类型 {ftype}（支持 {sorted(TYPES)}）')
        if not f.get('label'):
            warns.append(f'⚠ {name}: 缺 label（生成后问题文本为空）')
        elif re.search(r'[<>=\-]', str(f.get('label'))):
            warns.append(f'⚠ {name}: label 含数学/范围符号（生成时会自动转中文：>大于 <小于 =等于 >=大于等于 <=小于等于 -至）')
        # 选项
        opts = f.get('options')
        if isinstance(opts, str):
            opts = [o for o in opts.split('\n') if o.strip()]
        if isinstance(opts, list) and opts:
            nums = []
            for o in opts:
                m = re.match(r'^【?(\d+)】?', str(o))
                if m:
                    nums.append(int(m.group(1)))
                else:
                    warns.append(f'⚠ {name}: 选项 "{o}" 无【编号】格式')
            if len(nums) != len(set(nums)):
                errs.append(f'✗ {name}: 选项编号重复')
            if nums and max(nums) != len(set(nums)):
                missing = [n for n in range(1, max(nums) + 1) if n not in nums]
                warns.append(f'⚠ {name}: 选项编号跳号，缺 {missing}')
            # 编号位数 vs 数字掩码（仅显式 digits 检查；无 digits 由生成器自动匹配位数）
            if ftype == 'number' and nums:
                digits = str(f.get('digits', ''))
                if digits and digits.split('.')[0].isdigit():
                    need = len(str(max(nums)))
                    if int(digits.split('.')[0]) < need:
                        errs.append(f'✗ {name}: 显式 digits={digits} 装不下编号 {max(nums)}（需 {need} 位）')
            # 其他 → 注明字段
            if any(w in str(o) for o in opts for w in OTHER_WORDS):
                o_name = name + 'O' if name[-1] != 'O' else name
                if len(o_name) > 10:
                    errs.append(f'✗ {name}: 自动注明字段 {o_name} 超 10 字符（{len(o_name)}），请缩短基础字段名')
                elif o_name not in names and o_name not in {x['name'] for x in fields}:
                    warns.append(f'⚠ {name}: 含"其他"选项但未见注明字段 {o_name}（qes 会自动补齐，若 JSON 想显式定义请加）')
        # 掩码
        if ftype == 'number':
            digits = f.get('digits')
            if digits is not None:
                d = str(digits)
                if not re.match(r'^\d+(\.\d+)?$', d):
                    errs.append(f'✗ {name}: digits "{d}" 非法（应为 "11" 或 "2.1"）')
        elif ftype == 'date':
            df = f.get('date_format', '<yyyy/mm/dd>')
            if df not in VALID_DATES:
                errs.append(f'✗ {name}: 非法日期格式 {df}（仅 6 种）')
        elif ftype in ('text', 'memo'):
            ln = f.get('length')
            if ln is not None and (not str(ln).isdigit() or int(ln) <= 0):
                errs.append(f'✗ {name}: length {ln} 非法（正整数）')
        # 规则引用
        for jv in (f.get('jumps') or {}).values():
            if jv not in ('NEXT', 'END', 'WRITE') and jv not in names and jv not in {x['name'] for x in fields}:
                errs.append(f'✗ {name}: jumps 目标 {jv} 不存在')
        rg = f.get('range')
        if rg and not (isinstance(rg, (list, tuple)) and len(rg) == 2):
            if not (isinstance(rg, str) and re.match(r'^\S+\s+\S+$', rg)):
                errs.append(f'✗ {name}: range 非法（应为 [min,max] 或 "min max"）')
        legal = f.get('legal')
        if legal and not isinstance(legal, (list, tuple)):
            errs.append(f'✗ {name}: legal 应为数组')

    return errs, warns


def main():
    ap = argparse.ArgumentParser(description='字段定义 JSON 预校验')
    ap.add_argument('json', help='字段定义 JSON 文件')
    ap.add_argument('-o', '--output', help='报告输出文件（UTF-8）')
    args = ap.parse_args()
    try:
        data = json.load(open(args.json, encoding='utf-8'))
    except Exception as e:
        print(f'✗ {args.json}: JSON 解析失败: {e}')
        sys.exit(1)
    errs, warns = collect_errors_warns(data)
    title = data.get('title', args.json)
    L = ['═' * 46, f'字段 JSON 预校验: {title}', '─' * 46,
         f'字段总数: {len(data.get("fields", []))}']
    for e in errs:
        L.append(e)
    for w in warns:
        L.append(w)
    L.append('─' * 46)
    if not errs and not warns:
        L.append('✓ 全部通过，无错误无警告')
        code = 0
    elif errs:
        L.append(f'✗ {len(errs)} 个错误（需修复） | {len(warns)} 个警告')
        code = 1
    else:
        L.append(f'✓ 无错误，{len(warns)} 个警告（可不处理）')
        code = 2
    report = '\n'.join(L) + '\n'
    print(report)
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='') as f:
            f.write(report)
    sys.exit(code)


if __name__ == '__main__':
    main()
