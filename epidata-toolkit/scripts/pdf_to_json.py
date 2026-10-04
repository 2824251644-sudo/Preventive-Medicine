#!/usr/bin/env python3
"""PDF 调查表 → 字段定义 JSON 草稿（半自动，输出后需人工核对）

用法:
  python3 scripts/pdf_to_json.py 调查表.pdf -o 字段定义.json [--ocr] [--dpi 200] [--no-report]

流程:
  1. 文本提取：优先 pdftotext（有文本层的 PDF）；扫描版需 --ocr（pdftoppm 转图 + tesseract chi_sim）
  2. 启发式解析：按"编号 + 掩码/选项/冒号"切问题行，推断类型与掩码
  3. 输出 JSON 草稿 + 核对报告（哪些行未解析、可疑行）

掩码推断（OCR 文本特征 → EpiData 类型）:
  口口口口年口口月口口日口口时口口分 → date + time（拆成 字段DT/字段TM 两个字段）
  口口口口年口口月口口日            → date（yyyy）
  口口日/口口月口口日              → date（dd/mm/yyyy）
  口口时口口分                     → time（##时##分）
  口口×N（身份证类）                → number，位数=N
  电话/手机/传真                  → number digits=11
  口选项A 口选项B …              → number + options【1】A【2】B…
  下划线 ___                      → text，长度=下划线数
  其余                            → text（length 按填框宽度估算，默认 10）

字段名自动生成 Q1/Q2/…（顺序编号），人工核对后建议改名（拼音/缩写），
可提供 --names 映射 {"Q1": "FIRSTUNIT"} 替换。

注意: OCR 有噪声（如 吕→日、口=填框），输出必须人工核对后使用。
"""
import argparse, json, os, re, subprocess, sys, tempfile

# 掩码特征 → 类型
DATE_YMD_RE = re.compile(r'口{4}年口{2}月口{2}日')
DATE_DMY_RE = re.compile(r'口{2}月口{2}日')
TIME_RE = re.compile(r'口{2}时口{2}分')
BOX_RE = re.compile(r'口+')
OPT_RE = re.compile(r'口\s*([^口]{1,12}?)(?=口|$|\s{2,})')
UNDER_RE = re.compile(r'_+')
NUM_RE = re.compile(r'^\s*(?:(\d+)[\.、．]?\s*)?(?:[一二三四五六七八九十]+[\.、．]\s*)?(\d+)?[\.、．]\s*')


def extract_text(pdf, use_ocr, dpi, workdir):
    """返回页列表（每页文本）"""
    pages = []
    if not use_ocr:
        try:
            out = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True)
            text = out.stdout.decode('utf-8', errors='replace')
            if text.strip():
                pages = [text]
        except Exception:
            pass
    if not pages:
        if not use_ocr:
            print('⚠ pdftotext 无文本（扫描版？），改用 OCR…')
        # pdftoppm → tesseract
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', pdf,
                        os.path.join(workdir, 'page')], check=True)
        import glob
        for img in sorted(glob.glob(os.path.join(workdir, 'page*.png'))):
            base = img[:-4]
            subprocess.run(['tesseract', img, base, '-l', 'chi_sim'],
                           capture_output=True)
            pages.append(open(base + '.txt', encoding='utf-8').read())
    return pages


def clean_line(s):
    """清理 OCR 噪声（保留 口 填框符）"""
    s = s.replace('吕', '日').replace('口口口口口口口口口口口口口口口口口口口口口口', '')
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip()


def infer_field(text, qno, prev_lines):
    """从一行问题文本推断字段定义；返回 [字段] 或 []（无法解析）"""
    fields = []
    t = clean_line(text)
    if not t or t.startswith(('附表', '附件', '说明', '填表')):
        return fields, None
    if re.match(r'^[一二三四五六七八九十]+、', t):  # 章节标题
        return fields, None
    # 拆多问题一行：(1)电话 (2)传真 (3)E-mail
    subs = re.split(r'[（(]\d+[）)]', t)
    if len(subs) > 2:
        head = subs[0]
        for i, sub in enumerate(subs[1:], 1):
            sub = (head if i == 1 else '') + sub  # 首个子问题带原问题头
            f, _ = infer_field(sub, f'{qno}{chr(64 + i)}', prev_lines)
            fields.extend(f)
        return fields, None
    # 选项：口A 口B（横排）
    opt_parts = re.findall(r'口\s*([^口]{1,12}?)(?=口|$)', t)
    label = re.sub(r'口\s*([^口]{1,12}?)(?=口|$)', '', t).strip(' :：。.·口')
    label = re.sub(r'\s+', '', label)
    has_other = '其他' in t or '其它' in t
    if opt_parts and not re.search(r'年口{2}月|时口{2}分', t):
        opts = [f'【{i}】{p.strip()}' for i, p in enumerate(opt_parts, 1)]
        f = {'name': f'Q{qno}', 'type': 'number', 'label': label, 'options': '\n'.join(opts)}
        if has_other:
            f['other'] = True
        return [f], f
    # 日期时间
    if DATE_YMD_RE.search(t):
        name = f'Q{qno}'
        base = label.rstrip('：:')
        if TIME_RE.search(t):
            return [{'name': name, 'type': 'date', 'label': base, 'date_format': '<yyyy/mm/dd>'},
                    {'name': name + 'TM', 'type': 'time', 'label': base}], None
        return [{'name': name, 'type': 'date', 'label': base, 'date_format': '<yyyy/mm/dd>'}], None
    if DATE_DMY_RE.search(t):
        return [{'name': f'Q{qno}', 'type': 'date', 'label': label, 'date_format': '<dd/mm/yyyy>'}], None
    if TIME_RE.search(t):
        return [{'name': f'Q{qno}', 'type': 'time', 'label': label}], None
    # 身份证/长数字
    box_count = len(BOX_RE.findall(t))
    if box_count >= 15 and ('身份' in t or '证号' in t):
        return [{'name': f'Q{qno}', 'type': 'number', 'label': label, 'digits': str(box_count)}], None
    # 电话
    if re.search(r'电话|手机|传真|E-mail', t):
        d = 11 if re.search(r'手机|电话', t) else 15
        return [{'name': f'Q{qno}', 'type': 'number', 'label': label, 'digits': str(d)}], None
    # 下划线长度
    if UNDER_RE.search(t):
        ln = max(len(m) for m in UNDER_RE.findall(t))
        return [{'name': f'Q{qno}', 'type': 'text', 'label': label, 'length': ln}], None
    # 无特征 → text
    return [{'name': f'Q{qno}', 'type': 'text', 'label': label, 'length': 10}], None


def main():
    ap = argparse.ArgumentParser(description='PDF 调查表 → 字段 JSON 草稿')
    ap.add_argument('pdf', help='PDF 调查表')
    ap.add_argument('-o', '--output', required=True, help='输出 JSON 路径')
    ap.add_argument('--ocr', action='store_true', help='强制 OCR（扫描版 PDF）')
    ap.add_argument('--dpi', type=int, default=200, help='OCR 分辨率（默认 200）')
    ap.add_argument('--names', help='字段名映射 {"Q1": "FIRSTUNIT"}（替换自动名）')
    ap.add_argument('--no-report', action='store_true', help='不生成核对报告')
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as workdir:
        pages = extract_text(args.pdf, args.ocr, args.dpi, workdir)
    text = '\n'.join(pages)
    print(f'✓ 提取文本 {len(text)} 字符（{len(pages)} 页）')

    # 行解析
    lines = [clean_line(l) for l in text.split('\n')]
    fields, qno, unresolved = [], 0, []
    for i, ln in enumerate(lines):
        if not ln:
            continue
        f_list, f = infer_field(ln, qno + 1, lines[max(0, i - 1):i])
        if not f_list:
            if re.search(r'[一-龥]', ln) and not ln.startswith(('附表', '附件', '填表')):
                unresolved.append(ln[:40])
            continue
        for fld in f_list:
            qno += 1
            fld['name'] = f'Q{qno}'
            fields.append(fld)

    # 名称映射
    if args.names:
        mp = json.load(open(args.names, encoding='utf-8'))
        for f in fields:
            if f['name'] in mp:
                f['name'] = mp[f['name']]
                f['manual'] = True

    out = {'title': os.path.splitext(os.path.basename(args.pdf))[0], 'fields': fields}
    with open(args.output, 'w', encoding='utf-8', newline='') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f'✓ 已写入 {args.output}：{len(fields)} 个字段（自动名 Q1..Q{len(fields)}，建议人工核对后改名）')

    # 核对报告
    if not args.no_report:
        rep = args.output.rsplit('.', 1)[0] + '_核对报告.txt'
        L = [f'PDF→JSON 核对报告: {args.pdf}', f'字段 {len(fields)} 个', '',
             '⚠ 以下行未能解析（可能是标题/表格/OCR 噪声，请人工核对是否漏字段）:']
        L += [f'  {u}' for u in unresolved[:80]]
        if len(unresolved) > 80:
            L.append(f'  … 其余 {len(unresolved) - 80} 行略')
        L.append('')
        L.append('⚠ 检查建议: 1) 字段名 Q1.. 请改为有意义的拼音/缩写；'
                 '2) 选项字段核对编号与文案；3) 含"其他"的字段需配注明字段（字段名+O）；'
                 '4) 跑 validate_fields.py 预校验后再生成 qes/chk。')
        with open(rep, 'w', encoding='utf-8', newline='') as fh:
            fh.write('\n'.join(L) + '\n')
        print(f'✓ 核对报告: {rep}（未解析行 {len(unresolved)}）')


if __name__ == '__main__':
    main()
