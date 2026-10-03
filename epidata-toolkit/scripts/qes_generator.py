#!/usr/bin/env python3
"""qes_generator.py - 根据 JSON 字段定义生成 EpiData qes 文件（标准格式）。

用法:
    qes_generator.py <input.json> -o <output.qes>
    qes_generator.py <input.json> -o <output.qes> --encoding utf-8 --newline lf

JSON 输入格式:
{
  "title": "调查表名称",
  "sections": [{"field": "SEX", "title": "1. 一般情况"}],   # 章节标题（普通文本行）
  "fields": [
    {"name": "NAME", "type": "text", "length": 4, "label": "姓名"},
    {"name": "SEX", "type": "number", "digits": 1, "label": "性别",
     "options": ["【1】男", "【2】女"]},
    {"name": "MAXX", "type": "number", "digits": "2.1", "label": "最高体温（℃）"},
    {"name": "ONSETDT", "type": "date", "label": "发病日期"},
    {"name": "ONSETTM", "type": "time", "label": "发病时间"},
    {"name": "SUMMARY", "type": "memo", "length": 20, "label": "小结"}
  ]
}

字段类型映射（标准格式）:
    number  digits: int(位数) 或 str("整数位.小数位")   -> # / ##.#
    text    length: 中文字数（输出 2*length 个下划线，两_=一字） -> ____
    date    六种格式之一: <dd/mm/yyyy> <mm/dd/yyyy> <yyyy/mm/dd>
             <Today-dmy> <Today-mdy> <Today-ymd>（默认 <dd/mm/yyyy>，可用 date_format 指定）
    time    无 <hh:mm>！输出 ##时##分
    memo    length: 中文字数 -> 长下划线

行格式规范（EpiData 标准）:
    {变量名}问题文本掩码[选项]
    例: {sex}性别：#【1】男  【2】女
"""

import argparse
import json
import re
import sys

VALID_DATES = ["<dd/mm/yyyy>", "<mm/dd/yyyy>", "<yyyy/mm/dd>",
               "<Today-dmy>", "<Today-mdy>", "<Today-ymd>"]



# GBK 无法编码字符的自动替换表。
# 实测：GBK 原生支持 ℃±×÷≤≥μ、罗马数字Ⅰ-Ⅻ、≠≈→←√∞…·—–°′″ 等医学常用符号，
# 仅上标/下标数字无法编码，必须替换（见 references/gbk_chars.md）。
GBK_REPLACE = {
    # 上标数字 → ^n（GBK 不支持，如 ×10⁹/L → ×10^9/L）
    "⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4",
    "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9",
    # 下标数字 → 数字
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
}

def apply_gbk_replace(content):
    """替换 GBK 无法编码的字符；返回 (新内容, 已替换映射列表, 仍不可编码字符集)"""
    bad_before = sorted({c for c in content if not _gbk_ok(c)})
    if not bad_before:
        return content, [], set()
    replaced, still_bad = {}, set()
    for c in bad_before:
        if c in GBK_REPLACE:
            content = content.replace(c, GBK_REPLACE[c])
            replaced[c] = GBK_REPLACE[c]
        else:
            still_bad.add(c)
    return content, list(replaced.items()), still_bad

def _gbk_ok(c):
    try:
        c.encode("gbk")
        return True
    except UnicodeEncodeError:
        return False



def infer_date_format(label):
    """日期格式自动推断：按 label 中"年月日"连续提示（可夹空格）推断填写顺序。
    年 月 日 → <yyyy/mm/dd>；日 月 年 → <dd/mm/yyyy>；月 日 年 → <mm/dd/yyyy>。
    无提示（如"发现日期"）返回 None，由调用方用默认格式。
    用正则匹配连续顺序，避免"日期"里的"日"字干扰（find 会误命中）。"""
    lab = label or ""
    if re.search(r"年\s*月\s*日", lab):
        return "<yyyy/mm/dd>"
    if re.search(r"日\s*月\s*年", lab):
        return "<dd/mm/yyyy>"
    if re.search(r"月\s*日\s*年", lab):
        return "<mm/dd/yyyy>"
    return None


def build_mask(field):
    """根据字段定义生成 EpiData 掩码。"""
    ftype = field.get("type", "").lower()
    if ftype == "number":
        digits = field.get("digits", 1)
        if isinstance(digits, int):
            if digits < 1:
                raise ValueError(f"字段 {field.get('name')}: digits 必须 >= 1")
            return "#" * digits
        if isinstance(digits, str) and re.fullmatch(r"\d+\.\d+", digits):
            int_part, dec_part = digits.split(".")
            return "#" * int(int_part) + "." + "#" * int(dec_part)
        raise ValueError(f"字段 {field.get('name')}: digits 必须是整数或 '整数.小数' 格式")
    if ftype in ("text", "memo"):
        # 文本字段用下划线：两个 _ = 一个中文字
        length = int(field.get("length", 10))
        if length < 1:
            raise ValueError(f"字段 {field.get('name')}: length 必须 >= 1（中文字数）")
        return "_" * (length * 2)
    if ftype == "date":
        fmt = field.get("date_format") or infer_date_format(field.get("label", "")) or "<dd/mm/yyyy>"
        if fmt not in VALID_DATES:
            raise ValueError(f"字段 {field.get('name')}: 非法日期格式 '{fmt}'，仅支持 {VALID_DATES}")
        return fmt
    if ftype == "time":
        # EpiData 无 <hh:mm>，具体时间用 ##时##分
        return "##时##分"
    raise ValueError(f"字段 {field.get('name')}: 未知类型 '{ftype}'（支持 number/text/date/time/memo）")


def validate_field_name(name):
    """校验字段名：字母开头，仅字母数字，<=10 字符。"""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name):
        raise ValueError(f"非法字段名 '{name}': 必须以字母开头，仅含字母数字")
    if len(name) > 10:
        raise ValueError(f"字段名 '{name}' 超过 10 字符（EpiData 限制）")
    return name.upper()



def auto_expand_other(fields):
    """自动补齐"其他/其它"注明字段：选项含"其他/其它"且未显式定义 字段名+O 时，
    紧跟主字段后自动插入一个文本注明栏（label 取选项原文如 【18】其他）。
    保证 qes 与 chk 联动（chk 自动生成"其他"跳转时目标一定存在）。"""
    names = {f.get("name", "") for f in fields}
    out = []
    for f in fields:
        out.append(f)
        opts = f.get("options") or []
        if isinstance(opts, str):
            opts = [o for o in opts.split("\n") if o.strip()]
        other_num = None
        for o in opts:
            m = re.match(r"【(\d+)】([^【】]*)", str(o))
            if m and ("其他" in m.group(2) or "其它" in m.group(2)):
                other_num = m.group(1)
                break
        if other_num is None:
            continue
        other_label = str(o).strip()  # 注明字段 label 取选项原文（如 【6】其它）
        o_name = f["name"] + "O"
        # 显式同源注明字段优先（兼容简化命名，如 HANDWASO）：跳过自动生成
        if o_name in names or f["name"][:-1] + "O" in names:
            continue
        out.append({"name": o_name, "type": "text", "length": 8,
                    "label": other_label, "auto_other": True})
        names.add(o_name)
    return out



def auto_digits(field, opts):
    """掩码位数自动匹配：number 字段未显式 digits 时，按选项编号最大位数自动设置。
    例: 选项编号到【10】以上时自动用 ##（1位#容纳不下会截断录入）。"""
    if field.get("type", "").lower() != "number" or "digits" in field:
        return
    nums = []
    for o in opts:
        m = re.match(r"【(\d+)】", str(o))
        if m:
            nums.append(int(m.group(1)))
    if nums:
        field["digits"] = max(1, len(str(max(nums))))


def generate_qes(data):
    """生成 qes 文本内容（按行返回）。

    标准行格式:
        {变量名}问题文本掩码  选项（【1】男  【2】女 同行）
    章节标题/说明 = 普通文本行（不以 # 开头，不以 { 开头）
    """
    lines = []
    title = data.get("title", "EpiData 调查表")
    lines.append(title)

    sections = {}
    for s in data.get("sections", []):
        sections[s.get("field")] = s.get("title")

    seen = set()
    fields = auto_expand_other(data.get("fields", []))
    if not fields:
        raise ValueError("fields 不能为空")

    for field in fields:
        name = validate_field_name(field.get("name", ""))
        if name in seen:
            raise ValueError(f"字段名 '{name}' 重复")
        seen.add(name)

        # 章节标题（配置在对应字段之前，普通文本行）
        if name in sections:
            lines.append(f"{sections[name]}")

        # 选项同行: 【1】男  【2】女（双空格分隔）
        opts = field.get("options", "")
        if isinstance(opts, str):
            opts = [o for o in opts.split("\n") if o.strip()]
        auto_digits(field, opts)   # 掩码位数自动匹配（在 build_mask 前）
        mask = build_mask(field)

        # 行: {变量}问题文本掩码
        label = str(field.get("label", "")).strip()
        if label and not label.startswith("【") and not re.search(r"[:：?？。]$", label):
            label += "："  # 全角冒号（与标准示范一致）；【n】选项注明行不加冒号
        line = f"{{{name}}}{label}{mask}"

        if opts:
            line += "  " + "  ".join(str(o).strip() for o in opts)
        lines.append(line)

    return lines


def main():
    parser = argparse.ArgumentParser(description="生成 EpiData qes 文件（标准格式）")
    parser.add_argument("input", help="字段定义 JSON 文件")
    parser.add_argument("-o", "--output", required=True, help="输出 qes 文件路径")
    parser.add_argument("--encoding", default="gbk", choices=["utf-8", "gbk"],
                        help="输出编码（默认 gbk，兼容 EpiData 3.1 中文版）")
    parser.add_argument("--newline", default="crlf", choices=["crlf", "lf"],
                        help="输出行尾（默认 crlf，EpiData 兼容）")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        lines = generate_qes(data)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    content = "\n".join(lines) + "\n"
    newline = "\r\n" if args.newline == "crlf" else "\n"
    content = content.replace("\n", newline)

    # GBK 兼容性预检：EpiData 3.1 中文版只支持 GBK。
    # 先自动替换上标/罗马数字等 GBK 不支持的字符（⁹→^9 等），替换后仍不可编码才报错
    if args.encoding == "gbk":
        content, replaced, still_bad = apply_gbk_replace(content)
        if replaced:
            shown = ", ".join(f"{k}→{v}" for k, v in replaced[:10])
            print(f"⚠ 已自动替换 GBK 不支持字符 {len(replaced)} 处: {shown}")
        if still_bad:
            print(f"错误: 内容含 GBK 无法编码的字符 {''.join(sorted(still_bad))}（EpiData 3.1 中文版不支持，且无自动替换规则）", file=sys.stderr)
            print("提示: 请手动改为 GBK 支持的写法", file=sys.stderr)
            sys.exit(1)

    try:
        with open(args.output, "w", encoding=args.encoding, newline="") as f:
            f.write(content)
        print(f"✓ 已生成 {args.output}（{args.encoding}，{args.newline}，{len(lines)} 行）")
    except OSError as e:
        print(f"写入失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
