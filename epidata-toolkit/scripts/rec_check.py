#!/usr/bin/env python3
"""rec↔qes 结构校验：比对 EpiData 调查表(qes)与数据文件(rec)的字段结构与顺序

用法:
  python3 scripts/rec_check.py <survey.qes> <data.rec> [-o 报告.txt]

校验项:
  1. 字段数量（rec 自动追加的 ID 字段自动跳过，不误报）
  2. 字段名称双向一致（qes 有 rec 无 / rec 有 qes 无）
  3. 字段顺序一致（错位会严重影响双录入比对与数据理解）

rec 字段定义区过滤规则（基于 v3 真实 rec 567 行校准）:
  - 真实数据字段：类型列(第2个数字)≤10 且 类型码列(第7个数字)>0
  - _LABELn 标题段（章节标题/说明）：类型码列=0 → 跳过
  - _LABELn 选项标签段（【1】男  【2】女 等选项文本）：类型列>10 → 跳过
  - 掩码中文显示段（##时##分 拆出的"时"字，如 FOUNDTM1 类型18/20/21）：类型列>10 → 跳过
    注意：这些段名是"字段名+数字后缀"（FOUNDTM1/REPTM1/NETREPTM1），易被误当数据字段
"""
import argparse, re, sys

FIELD_PAT = re.compile(
    r'^\s*([#_]?)([A-Za-z][A-Za-z0-9]*)\s+(\d+)\s+(\d+)\s+30\s+(\d+)\s+\d+\s+(\d+)\s+(\d+)\s+112\s+'
)
# 数字列: 类型 序号 30 起始 长度 小数 类型码 112
# group(3)=类型列（≤10 数据字段；>10 选项标签/掩码中文段）
# group(7)=类型码列（>0 数据字段；0 标题段）
# EpiData 生成 rec 时自动追加的 ID 字段名（在 qes 中不存在）
REC_ONLY_ID = ("ID", "_ID", "IDCODE")


def parse_rec_fields(path):
    """返回 rec 数据字段名列表（按定义顺序，过滤标题段/选项标签段/掩码中文段）"""
    raw = open(path, 'rb').read()
    first = raw.find(b'\r\n')
    if first < 0:
        raise SystemExit(f'✗ {path}: 未找到 CRLF，非 EpiData rec 文本格式')
    head = raw[:first].decode('gbk', errors='replace').strip().split()
    if len(head) < 2:
        raise SystemExit(f'✗ {path}: 首行格式异常: {raw[:first]!r}')
    n_fields = int(head[0])
    names = []
    pos = first + 2
    for _ in range(n_fields):
        eol = raw.find(b'\r\n', pos)
        if eol < 0:
            raise SystemExit(f'✗ {path}: 字段定义区在第 {len(names)} 个字段后提前结束')
        ln = raw[pos:eol].decode('gbk', errors='replace')
        m = FIELD_PAT.match(ln)
        if not m:
            raise SystemExit(f'✗ {path}: 字段定义行无法解析: {ln[:80]!r}')
        # 真实数据字段：类型列≤10 且 类型码>0（标题段类型码0、选项标签/掩码中文段类型>10 均跳过）
        if int(m.group(3)) <= 10 and int(m.group(7)) > 0:
            names.append(m.group(2))
        pos = eol + 2
    return names


def parse_qes_fields(path):
    """返回 qes 字段名列表（按出现顺序，{变量} 提取）"""
    raw = open(path, 'rb').read()
    # 尝试 GBK / UTF-8 解码
    try:
        text = raw.decode('gbk')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    names = re.findall(r'\{([A-Za-z][A-Za-z0-9]*)\}', text)
    return names


def main():
    ap = argparse.ArgumentParser(description='rec↔qes 结构校验')
    ap.add_argument('qes', help='EpiData 调查表 .qes 文件')
    ap.add_argument('rec', help='EpiData 数据文件 .rec 文件')
    ap.add_argument('-o', '--output', help='报告输出文件（UTF-8）')
    args = ap.parse_args()

    q = parse_qes_fields(args.qes)
    r = parse_rec_fields(args.rec)

    # 去掉 rec 自动 ID 字段（若在开头且为 ID 类）
    r_wo = list(r)
    if r_wo and r_wo[0] in REC_ONLY_ID:
        r_wo = r_wo[1:]

    L = ['═' * 46, 'rec ↔ qes 结构校验报告', '─' * 46]
    L.append(f'qes : {args.qes}')
    L.append(f'      字段 {len(q)} 个')
    L.append(f'rec : {args.rec}')
    L.append(f'      字段 {len(r)} 个（自动 ID 已剔除后 {len(r_wo)} 个参与比对）')
    L.append('─' * 46)

    q_set, r_set = set(q), set(r_wo)
    only_q = [n for n in q if n not in r_set]
    only_r = [n for n in r_wo if n not in q_set]
    dup_q = [n for n in set(q) if q.count(n) > 1]
    dup_r = [n for n in set(r_wo) if r_wo.count(n) > 1]

    order_diff = 0
    if len(q) == len(r_wo):
        order_diff = sum(1 for a, b in zip(q, r_wo) if a != b)

    ok = True
    if only_q:
        ok = False
        L.append(f'✗ qes 有而 rec 无（{len(only_q)} 个）: {", ".join(only_q[:20])}')
    if only_r:
        ok = False
        L.append(f'✗ rec 有而 qes 无（{len(only_r)} 个）: {", ".join(only_r[:20])}')
    if dup_q:
        ok = False
        L.append(f'✗ qes 字段重复（{len(dup_q)} 个）: {", ".join(dup_q[:10])}')
    if dup_r:
        ok = False
        L.append(f'✗ rec 字段重复（{len(dup_r)} 个）: {", ".join(dup_r[:10])}')
    if order_diff:
        ok = False
        first_diff = next((i for i, (a, b) in enumerate(zip(q, r_wo)) if a != b), 0)
        L.append(f'✗ 字段顺序错位 {order_diff} 处（示例: 第{first_diff + 1}位 qes={q[first_diff]} vs rec={r_wo[first_diff]}）')
    if len(q) != len(r_wo):
        ok = False
        L.append(f'✗ 字段数量不一致: qes {len(q)} vs rec {len(r_wo)}（差值 {len(q)-len(r_wo)}）')

    if ok:
        L.append(f'✓ 结构与顺序完全一致：{len(q)} 个字段一一对应')
    L.append('─' * 46)
    report = '\n'.join(L) + '\n'
    print(report)
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='') as f:
            f.write(report)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
