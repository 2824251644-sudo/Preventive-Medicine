#!/usr/bin/env python3
"""生成 EpiData .chk 检查文件（标准格式，EpiData 3.1 真实保存格式）

标准结构（用户锚定，不可偏离）:
    字段名                  ← 裸字段名，无花括号、无缩进
      RANGE 1 5            ← 属性行，缩进2空格，上下限空格分隔，无等号
      LEGAL                ← 子块开启，缩进2空格
        1                  ← 子块内容，缩进4空格，每个合法值一行
      END                  ← 子块结束，缩进2空格
      JUMPS                ← 子块开启，缩进2空格
        5 REPWAYO          ← 跳转规则，缩进4空格：值 目标字段
      END                  ← 子块结束，缩进2空格
      MUSTENTER            ← 连写属性，缩进2空格
    END                    ← 字段块结束，无缩进

约束:
- 字段头不写 TYPE（类型由 qes 掩码决定）
- RANGE 与 LEGAL 互斥：有 options/legal 走 LEGAL 子块，只有 range 才写 RANGE
- 未确认结构（TYPE/AUTOENTER/NOENTER/KEY/REPEAT/VERIFY/BEFORE/AFTER）一律不生成

自动规则:
- "其他/其它"选项自动跳转：字段选项含"其他/其它"且存在注明字段（字段名+O 后缀）时，
  自动生成 JUMPS「其他编号 → 注明字段」（已有同值 jumps 时不覆盖）
- 仅输出已确认结构

用法:
  python3 chk_generator.py <fields.json> -o <output.chk> [--encoding gbk] [--newline crlf]

字段 JSON 可用规则:
  required: true            -> MUSTENTER
  range: [1,2] 或 "1-2"     -> RANGE 1 2（空格分隔）
  options / legal           -> LEGAL 子块（选项编号逐行）
  jumps: {"1": "FIELD"}     -> JUMPS 子块（值 目标字段），与自动"其他"跳转合并
"""
import argparse, json, re, sys

def opt_numbers(f):
    nums = []
    for o in f.get("options", []):
        m = re.match(r"【(\d+)】", o)
        if m:
            nums.append(int(m.group(1)))
    return nums

def auto_other_jumps(f, all_names):
    """自动"其他"跳转：选项含其他/其它 → 注明字段（字段名+O）"""
    jumps = dict(f.get("jumps") or {})
    for o in f.get("options", []):
        m = re.match(r"【(\d+)】([^【】]*)", o)
        if m and ("其他" in m.group(2) or "其它" in m.group(2)):
            num = m.group(1)
            target = f["name"] + "O"
            if target in all_names and num not in jumps:
                jumps[num] = target
    return jumps or None

def main():
    ap = argparse.ArgumentParser(description="生成 EpiData chk 检查文件（标准格式）")
    ap.add_argument("input", help="字段定义 JSON 文件")
    ap.add_argument("-o", "--output", required=True, help="输出 chk 文件路径")
    ap.add_argument("--encoding", choices=["utf-8", "gbk"], default="gbk",
                    help="输出编码（默认 gbk，兼容 EpiData 3.1 中文版）")
    ap.add_argument("--newline", choices=["crlf", "lf"], default="crlf",
                    help="输出行尾（默认 crlf）")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    fields = data.get("fields", [])
    all_names = {f["name"] for f in fields}
    blocks = []

    for f in fields:
        name = f.get("name", "")
        if not name:
            print(f"错误: 存在无 name 的字段", file=sys.stderr)
            sys.exit(1)
        lines = [name]  # 裸字段名

        # RANGE（仅当有 range 且无 options/legal 时，二者互斥）
        nums = opt_numbers(f)
        legal = f.get("legal") or (nums if nums else None)
        rng = f.get("range")
        if rng and not legal:
            if isinstance(rng, (list, tuple)):
                rng_str = f"{rng[0]} {rng[1]}"
            else:
                rng_str = str(rng).replace('-', ' ')
            lines.append(f"  RANGE {rng_str}")

        # LEGAL 子块（选项/合法值，每个一行）
        if legal:
            lines.append("  LEGAL")
            for v in legal:
                lines.append(f"    {v}")
            lines.append("  END")

        # JUMPS 子块（显式 jumps + 自动"其他"跳转合并）
        jumps = auto_other_jumps(f, all_names)
        if jumps:
            lines.append("  JUMPS")
            for val, target in jumps.items():
                lines.append(f"    {val} {target}")
            lines.append("  END")

        # MUSTENTER（必填，连写）
        if f.get("required"):
            lines.append("  MUSTENTER")

        lines.append("END")  # 字段块结束（无缩进）
        blocks.append("\n".join(lines))

    content = "\n\n".join(blocks) + "\n"
    newline = "\r\n" if args.newline == "crlf" else "\n"
    content = content.replace("\n", newline)

    # GBK 预检
    if args.encoding == "gbk":
        try:
            content.encode("gbk")
        except UnicodeEncodeError as e:
            print(f"错误: 内容含 GBK 无法编码的字符 '{content[e.start]}'，请改用 ASCII", file=sys.stderr)
            sys.exit(1)

    with open(args.output, "w", encoding=args.encoding, newline="") as fh:
        fh.write(content)
    print(f"✓ 已生成 {args.output}（{args.encoding}，{args.newline}，{len(blocks)} 个字段块）")

if __name__ == "__main__":
    main()
