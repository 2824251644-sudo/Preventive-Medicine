#!/usr/bin/env python3
"""qes_validator.py - 校验 EpiData qes 文件（标准格式）。

用法:
    qes_validator.py <file.qes>

检查项:
    1. 编码可解码（UTF-8 或 GBK）
    2. BOM 检查（不应有）
    3. 行尾检查（应为 CRLF）
    4. 字段行格式: {变量名}问题文本掩码
    5. 变量名合法（字母开头、<=10 字符）且不重复
    6. 掩码合法:
       - 日期: <dd/mm/yyyy> <mm/dd/yyyy> <yyyy/mm/dd>
               <Today-dmy> <Today-mdy> <Today-ymd>（仅这 6 种）
       - 时间: ##时##分（无 <hh:mm>）
       - 数字: # 或 ##.#（可含一位小数点）
       - 文本: 下划线 _（两个 _ = 一个字，长度必须为偶数）

返回: 全部通过 exit 0；发现问题 exit 1。
"""

import argparse
import re
import sys

VALID_DATES = ["<dd/mm/yyyy>", "<mm/dd/yyyy>", "<yyyy/mm/dd>",
               "<Today-dmy>", "<Today-mdy>", "<Today-ymd>"]
DATE_PATTERN = re.compile(r"<(dd|mm|yyyy)/?[^>]*>")
TIME_PATTERN = re.compile(r"\d+时\d+分")
NUM_PATTERN = re.compile(r"#{1,11}(\.#{1,4})?")
UNDER_PATTERN = re.compile(r"_{2,}")
NAME_PATTERN = re.compile(r"^\{([A-Za-z][A-Za-z0-9]*)\}(.*)$")


def decode_file(path):
    """尝试 UTF-8 与 GBK 解码，返回 (text, encoding)。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None, None


def check_bom(path):
    return open(path, "rb").read(3) == b"\xef\xbb\xbf"


def check_newline(path):
    raw = open(path, "rb").read()
    cr, lf = raw.count(b"\r"), raw.count(b"\n")
    if cr == 0:
        return False, cr, lf
    return cr == lf, cr, lf


def mask_in_rest(rest):
    """在问题文本+掩码+选项的混合串中识别掩码。"""
    if any(d in rest for d in VALID_DATES):
        return True
    if TIME_PATTERN.search(rest):
        return True
    if NUM_PATTERN.search(rest):
        return True
    if UNDER_PATTERN.search(rest):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="校验 EpiData qes 文件（标准格式）")
    parser.add_argument("input", help="qes 文件路径")
    args = parser.parse_args()

    problems, infos = [], []

    text, encoding = decode_file(args.input)
    if text is None:
        problems.append("编码无法识别（既不是 UTF-8 也不是 GBK）")
    else:
        infos.append(f"编码: {encoding}")

    if check_bom(args.input):
        problems.append("发现 UTF-8 BOM（建议去除）")
    else:
        infos.append("BOM: 无")

    is_crlf, cr, lf = check_newline(args.input)
    if is_crlf:
        infos.append(f"行尾: CRLF（{cr} 行）")
    else:
        problems.append(f"行尾不是 CRLF（CR={cr}, LF={lf}）—— EpiData 生成 rec 会报错")

    # GBK 可编码性：老版 EpiData(3.1 中文版) 只能处理 GBK 字符
    if text:
        try:
            text.encode("gbk")
            infos.append("GBK 可编码性: 全部字符 GBK 可编码")
        except UnicodeEncodeError as e:
            problems.append(f"存在 GBK 无法编码的字符 '{text[e.start]}'(U+{ord(text[e.start]):04X})—— EpiData 3.1 中文版会乱码/报错，请改用 ASCII（如 ×10⁹/L → ×10^9/L）")

    field_count = 0
    seen = set()
    if text:
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or not stripped.startswith("{"):
                continue  # 章节标题/说明 = 普通文本行
            m = NAME_PATTERN.match(stripped)
            if not m:
                problems.append(f"第 {lineno} 行格式错误: [{stripped[:50]}]（应为 {{变量名}}问题文本掩码）")
                continue
            name, rest = m.group(1), m.group(2)
            field_count += 1
            if len(name) > 10:
                problems.append(f"第 {lineno} 行: 字段名 '{name}' 超过 10 字符")
            if name in seen:
                problems.append(f"第 {lineno} 行: 字段名 '{name}' 重复")
            seen.add(name)
            if "<hh:mm>" in rest:
                problems.append(f"第 {lineno} 行: 字段 '{name}' 含非法时间格式 <hh:mm>（应改用 ##时##分）")
            if DATE_PATTERN.search(rest):
                matched = DATE_PATTERN.search(rest).group(0)
                if matched not in VALID_DATES:
                    problems.append(f"第 {lineno} 行: 字段 '{name}' 日期格式 '{matched}' 非法，仅支持 {VALID_DATES}")
            if not mask_in_rest(rest):
                problems.append(f"第 {lineno} 行: 字段 '{name}' 未识别到掩码（日期6种/##时##分/#数字/偶数下划线）")
            # 下划线必须成对（两_=一字）
            for um in UNDER_PATTERN.finditer(rest):
                if len(um.group()) % 2 != 0:
                    problems.append(f"第 {lineno} 行: 字段 '{name}' 下划线 {len(um.group())} 个（应为偶数，两个_=一个字）")
                    break

    infos.append(f"字段数: {field_count}")

    print("=== qes 校验报告 ===")
    for info in infos:
        print(f"  [OK] {info}")
    if not problems:
        print("  [OK] 字段行格式、变量名、掩码全部合法，无重复")
        print("✓ 校验通过")
        return 0
    for p in problems:
        print(f"  [✗] {p}")
    print(f"✗ 发现 {len(problems)} 个问题")
    return 1


if __name__ == "__main__":
    sys.exit(main())
