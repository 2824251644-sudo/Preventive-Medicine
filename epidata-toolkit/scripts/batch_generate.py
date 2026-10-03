#!/usr/bin/env python3
"""批处理：目录下所有字段定义 JSON → 逐个生成 qes + txt + chk（复用 generate_all.py）

用法:
  python3 scripts/batch_generate.py <json目录> -o <输出目录> [--pattern *.json] [--encoding gbk] [--newline crlf]

输出: 每个 JSON 文件（去扩展名）作为输出基名，产出 <基名>.qes / .txt / .chk / _chk检查.txt
失败不中断，结束时汇总成功/失败数量。
"""
import argparse, glob, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="批处理：目录下所有字段 JSON 批量生成 qes/txt/chk")
    ap.add_argument("json_dir", help="字段定义 JSON 所在目录")
    ap.add_argument("-o", "--output", required=True, help="输出目录（不存在则创建）")
    ap.add_argument("--pattern", default="*.json", help="匹配的 JSON 文件模式（默认 *.json）")
    ap.add_argument("--encoding", choices=["gbk", "utf-8"], default="gbk",
                    help="qes/chk 输出编码（默认 gbk）")
    ap.add_argument("--newline", choices=["crlf", "lf"], default="crlf",
                    help="输出行尾（默认 crlf）")
    args = ap.parse_args()

    jsons = sorted(glob.glob(os.path.join(args.json_dir, args.pattern)))
    if not jsons:
        print(f"✗ {args.json_dir} 下没有匹配 {args.pattern} 的文件")
        sys.exit(1)
    os.makedirs(args.output, exist_ok=True)

    print(f"════ 批处理: {len(jsons)} 个 JSON → {args.output} ════")
    ok = fail = 0
    for j in jsons:
        base = os.path.splitext(os.path.basename(j))[0]
        out = os.path.join(args.output, base)
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "generate_all.py"), j, "-o", out,
             "--encoding", args.encoding, "--newline", args.newline],
            capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
            print(f"  ✓ {base}")
        else:
            fail += 1
            err = (r.stderr or "").strip().replace("\n", " ")
            print(f"  ✗ {base}: {err[:200]}")

    print(f"✓ 批处理完成：成功 {ok} / 失败 {fail}，输出目录: {args.output}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
