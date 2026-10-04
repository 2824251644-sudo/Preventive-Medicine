#!/usr/bin/env python3
"""rec → CSV / Excel 导出（录入数据喂给 SPSS / R / Excel 分析）

用法:
  python3 scripts/rec_export.py 数据.rec -o 导出路径 [--qes 调查表.qes] [-f csv|xlsx|both]

特性:
  - 复用 rec_compare 的解析（真实数据字段过滤：类型列≤10 且 类型码>0，掩码/选项/标题段跳过）
  - 表头用字段名（SPSS/R 友好）；提供 --qes 时提取中文标签（Excel 的"字典"表 / CSV 第二行）
  - CSV 用 UTF-8 带 BOM（Excel 双击打开中文不乱码）；xlsx 用 openpyxl
  - 空数据库（仅表头）正常导出
"""
import argparse, csv, re, sys
from rec_compare import parse_rec


def extract_labels(qes_path):
    """从 qes 提取 {字段名} → 中文标签（问题文本，去掩码与选项）"""
    raw = open(qes_path, 'rb').read()
    try:
        text = raw.decode('gbk')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    labels = {}
    for m in re.finditer(r'\{([A-Za-z][A-Za-z0-9]*)\}([^\{\r\n]*)', text):
        name, rest = m.group(1), m.group(2)
        # 标签 = {名} 后到第一个掩码字符（# _ <）前的文本；无掩码取全部
        cut = re.split(r'[#_<]', rest)[0]
        labels[name] = cut.strip()
    return labels


def main():
    ap = argparse.ArgumentParser(description='rec → CSV/Excel 导出')
    ap.add_argument('rec', help='EpiData 数据文件 .rec')
    ap.add_argument('-o', '--output', required=True, help='输出路径（无扩展名则按 -f 追加）')
    ap.add_argument('--qes', help='调查表 .qes（可选，提取中文标签）')
    ap.add_argument('-f', '--format', choices=['csv', 'xlsx', 'both'], default='csv')
    args = ap.parse_args()

    r = parse_rec(args.rec)
    labels = extract_labels(args.qes) if args.qes else {}
    names = [f['name'] for f in r['data_fields']]
    print(f"字段 {len(names)} 个 | 记录 {len(r['recs'])} 条 | 标签 {len(labels)} 个")

    def out_path(ext):
        base = args.output if not args.output.lower().endswith(('.csv', '.xlsx')) else args.output.rsplit('.', 1)[0]
        return base + ext

    # CSV
    if args.format in ('csv', 'both'):
        p = out_path('.csv')
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(names)
            if labels:
                w.writerow([labels.get(n, '') for n in names])
            for rec in r['recs']:
                w.writerow([rec[n] for n in names])
        print(f'✓ CSV 已写入 {p}（{len(r["recs"])} 行数据）')

    # Excel
    if args.format in ('xlsx', 'both'):
        from openpyxl import Workbook
        p = out_path('.xlsx')
        wb = Workbook()
        ws = wb.active
        ws.title = '数据'
        ws.append(names)
        if labels:
            ws.append([labels.get(n, '') for n in names])
        for rec in r['recs']:
            ws.append([rec[n] for n in names])
        # 字段字典表
        ws2 = wb.create_sheet('字段字典')
        ws2.append(['字段名', '中文标签', '存储宽度(字节)', '记录位置'])
        off = 0
        for f in r['data_fields']:
            ws2.append([f['name'], labels.get(f['name'], ''), f['width'], off])
            off += f['width']
        wb.save(p)
        print(f'✓ Excel 已写入 {p}（数据 + 字段字典 两个表）')


if __name__ == '__main__':
    main()
