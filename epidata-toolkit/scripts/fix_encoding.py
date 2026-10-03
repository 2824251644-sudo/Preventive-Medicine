#!/usr/bin/env python3
"""fix_encoding.py - 修复 qes/txt 文件的编码、行尾与 BOM。

用法:
    fix_encoding.py <input> -o <output>
    fix_encoding.py <input> -o <output> --encoding gbk --newline crlf --strip-bom
    fix_encoding.py <input> -o <output> --encoding utf-8 --newline lf

说明:
    - 默认自动检测输入编码（UTF-8 优先，失败则 GBK）
    - 默认输出: GBK 编码 + CRLF 行尾 + 无 BOM（EpiData 3.1 兼容）
"""

import argparse
import sys


def detect_encoding(raw):
    """检测输入编码：UTF-8 优先，失败则 GBK。"""
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("gbk")
        return "gbk"
    except UnicodeDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(description="修复 qes/txt 编码与行尾")
    parser.add_argument("input", help="输入文件")
    parser.add_argument("-o", "--output", required=True, help="输出文件")
    parser.add_argument("--encoding", default=None, choices=["utf-8", "gbk"],
                        help="输出编码（默认自动检测输入后原样保留）")
    parser.add_argument("--newline", default="crlf", choices=["crlf", "lf", "keep"],
                        help="输出行尾（默认 crlf）")
    parser.add_argument("--strip-bom", action="store_true", help="去除 UTF-8 BOM")
    parser.add_argument("--add-bom", action="store_true", help="添加 UTF-8 BOM")
    args = parser.parse_args()

    try:
        raw = open(args.input, "rb").read()
    except OSError as e:
        print(f"读取失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 检测输入编码
    src_enc = detect_encoding(raw)
    if src_enc is None:
        print("错误: 无法识别输入编码（既不是 UTF-8 也不是 GBK）", file=sys.stderr)
        sys.exit(1)

    # 去除 UTF-8 BOM
    if src_enc == "utf-8" and raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    # 解码
    text = raw.decode(src_enc)

    # 行尾统一为 \n 再转目标行尾
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if args.newline == "crlf":
        text = text.replace("\n", "\r\n")
    elif args.newline == "lf":
        pass  # 已是 \n

    # 输出编码
    out_enc = args.encoding if args.encoding else src_enc
    out = text.encode(out_enc)
    if args.add_bom:
        out = b"\xef\xbb\xbf" + out

    try:
        with open(args.output, "wb") as f:
            f.write(out)
        print(f"✓ 已修复: {args.input} → {args.output}")
        print(f"  编码: {src_enc} → {out_enc} | 行尾: {args.newline} | BOM: {'有' if args.add_bom else '无'}")
    except OSError as e:
        print(f"写入失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
