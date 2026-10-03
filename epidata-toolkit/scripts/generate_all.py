#!/usr/bin/env python3
"""一键生成：字段 JSON → qes + txt(检查版) + chk + chk检查txt

用法:
  python3 scripts/generate_all.py <fields.json> -o <基名>

产出（默认编码 GBK / 行尾 CRLF，兼容 EpiData 3.1 中文版）:
  <基名>.qes            EpiData 调查表（GBK+CRLF+无BOM）
  <基名>.txt            qes 的 UTF-8 查看版（记事本直接打开检查用）
  <基名>.chk            检查文件（标准格式，GBK+CRLF+无BOM）
  <基名>_chk检查.txt     chk 的 UTF-8 查看版

流程: qes_generator → chk_generator → fix_encoding(转查看版)
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd, desc):
    print(f"▶ {desc}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print("  " + r.stdout.strip().replace("\n", "\n  "))
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        print(f"✗ {desc} 失败，终止", file=sys.stderr)
        sys.exit(r.returncode)

def main():
    ap = argparse.ArgumentParser(description="一键生成 qes + txt + chk（EpiData 标准格式）")
    ap.add_argument("input", help="字段定义 JSON 文件")
    ap.add_argument("-o", "--output", required=True, help="输出基名（不含扩展名）")
    ap.add_argument("--encoding", choices=["gbk", "utf-8"], default="gbk",
                    help="qes/chk 输出编码（默认 gbk；查看版 txt 恒为 utf-8）")
    ap.add_argument("--newline", choices=["crlf", "lf"], default="crlf",
                    help="输出行尾（默认 crlf）")
    args = ap.parse_args()
    out = os.path.abspath(args.output)
    out_dir = os.path.dirname(out)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        print(f'  ✓ 已创建输出目录: {out_dir}')
    enc, nl = args.encoding, args.newline

    print(f"════ 一键生成: {out} ════")
    # 1. qes
    run([sys.executable, os.path.join(HERE, "qes_generator.py"), args.input,
         "-o", out + ".qes", "--encoding", enc, "--newline", nl],
        f"1/4 生成 {out}.qes（{enc}）")
    # 2. txt 检查版（qes → UTF-8）
    run([sys.executable, os.path.join(HERE, "fix_encoding.py"), out + ".qes",
         "-o", out + ".txt", "--encoding", "utf-8", "--newline", nl],
        f"2/4 生成 {out}.txt（UTF-8 检查版）")
    # 3. chk
    run([sys.executable, os.path.join(HERE, "chk_generator.py"), args.input,
         "-o", out + ".chk", "--encoding", enc, "--newline", nl],
        f"3/4 生成 {out}.chk（{enc}）")
    # 4. chk 检查版
    run([sys.executable, os.path.join(HERE, "fix_encoding.py"), out + ".chk",
         "-o", out + "_chk检查.txt", "--encoding", "utf-8", "--newline", nl],
        f"4/4 生成 {out}_chk检查.txt（UTF-8 查看版）")

    print(f"✓ 全部完成：{out}.qes / {out}.txt / {out}.chk / {out}_chk检查.txt")

if __name__ == "__main__":
    main()
