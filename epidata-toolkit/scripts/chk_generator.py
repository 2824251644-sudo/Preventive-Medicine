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
    opts = f.get("options", [])
    if isinstance(opts, str):
        opts = [o for o in opts.split("\n") if o.strip()]
    for o in opts:
        m = re.match(r"【(\d+)】", o)
        if m:
            nums.append(int(m.group(1)))
    return nums


# 常见数值字段自动 RANGE（保守表：只加有把握的，避免误伤）
RANGE_HINTS = [
    (("AGE",), "年龄", 0, 120),
    (("TEMP",), "体温", 30, 45),
]

def auto_range(f, name, label):
    """RANGE 自动推断：无 options 的 number 字段，字段名/标签命中保守表时自动生成 RANGE。
    显式 range 优先（此处仅在未配置 range 时被调用）。"""
    if f.get("options") or f.get("type", "").lower() != "number":
        return None
    up = name.upper()
    for keys, kw, lo, hi in RANGE_HINTS:
        if any(k in up for k in keys) or kw in (label or ""):
            return [lo, hi]
    return None


def auto_other_jumps(f, all_names):
    """自动"其他"跳转：选项含其他/其它 → 注明字段（字段名+O）"""
    jumps = dict(f.get("jumps") or {})
    opts = f.get("options") or []
    if isinstance(opts, str):
        opts = [o for o in opts.split("\n") if o.strip()]
    for o in opts:
        m = re.match(r"【(\d+)】([^【】]*)", o)
        if m and ("其他" in m.group(2) or "其它" in m.group(2)):
            num = m.group(1)
            target = f["name"] + "O"
            if target in all_names and num not in jumps:
                jumps[num] = target
    return jumps or None


def auto_labels(fields):
    """LABELBLOCK 值标签（EpiData 3.1 真实格式）：从选项【n】文本自动提取 编号→文本 映射。
    返回 {字段名: {编号: 文本}}。字段 JSON 显式 labelblock: false 时跳过（如长文本选项）。
    LABEL 命名规则：label_ + 字段名小写（用户样例 label_sex / label_marital）。"""
    labels = {}
    for f in fields:
        if f.get("labelblock") is False:
            continue
        opts = f.get("options") or []
        if isinstance(opts, str):
            opts = [o for o in opts.split("\n") if o.strip()]
        pairs = {}
        for o in opts:
            m = re.match(r"【(\d+)】(.+)", str(o).strip())
            if m:
                pairs[int(m.group(1))] = m.group(2).strip()
        if pairs:
            labels[f["name"]] = pairs
    return labels


def build_labelblock(labels):
    """LABELBLOCK 文件头块（用户锚定格式，不可偏离）：
    LABELBLOCK
      LABEL label_sex
        1  男
        2  女
      END
    END"""
    if not labels:
        return None
    lines = ["LABELBLOCK"]
    for fname, pairs in labels.items():
        lines.append(f"  LABEL label_{fname.lower()}")
        for n in sorted(pairs):
            lines.append(f"    {n}  {pairs[n]}")
        lines.append("  END")
    lines.append("END")
    return "\n".join(lines)


def auto_expand_other(fields):
    """与 qes_generator 相同的自动补齐逻辑：选项含"其他/其它"且无 字段名+O 时，
    自动插入注明字段（文本，无规则），保证 chk 字段块数与 qes 一致、跳转目标存在。"""
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
        if o_name in names or f["name"][:-1] + "O" in names:
            continue  # 显式同源注明字段优先（兼容简化命名，如 HANDWASO）
        out.append({"name": o_name, "type": "text", "length": 8,
                    "label": other_label, "auto_other": True})
        names.add(o_name)
    return out



# 必填自动推荐规则表（保守：字段名精确匹配，避免 FARMNAME/CASENAME 被 NAME 误伤）
REQUIRED_EXACT = {
    "NAME", "SEX", "AGE", "AGEM", "OCCUP", "ONSETDT", "OUTCOME", "ADDRESS",
    "MOBILE", "TEL", "TEL1", "BIRTHDT", "DIAGUNIT", "SURVDT", "SURVTM",
    "SURVNAME", "SURVUNIT", "INVDT", "INVNAME", "SIGN", "SURVSIGN",
}
REQUIRED_LABEL_KW = ("发病日期", "出生日期", "最终诊断", "现住址",
                     "调查时间", "调查人", "签名", "随访日期", "随访单位")

def auto_required(f, name, label, opts):
    """必填自动推荐：显式 required 优先；核心信息字段（精确匹配）、
    标签命中核心关键词、或含'不知道/不详'兜底选项的字段自动推荐。"""
    if "required" in f:
        return f["required"]
    if name in REQUIRED_EXACT:
        return True
    if any(kw in (label or "") for kw in REQUIRED_LABEL_KW):
        return True
    # 有"不知道/不清楚/不详"兜底选项的字段（多为暴露史），必填不会卡录入
    if any(("不知道" in str(o)) or ("不清楚" in str(o)) or ("不详" in str(o)) for o in opts):
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="生成 EpiData chk 检查文件（标准格式）")
    ap.add_argument("input", help="字段定义 JSON 文件")
    ap.add_argument("-o", "--output", required=True, help="输出 chk 文件路径")
    ap.add_argument("--encoding", choices=["utf-8", "gbk"], default="gbk",
                    help="输出编码（默认 gbk，兼容 EpiData 3.1 中文版）")
    ap.add_argument("--newline", choices=["crlf", "lf"], default="crlf",
                    help="输出行尾（默认 crlf）")
    ap.add_argument("--auto-required", action=argparse.BooleanOptionalAction, default=True,
                    help="必填自动推荐（默认开；--no-auto-required 关闭，仅用显式 required）")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    fields = auto_expand_other(data.get("fields", []))
    all_names = {f["name"] for f in fields}
    labels = auto_labels(fields)
    labelblock = build_labelblock(labels)
    blocks = []

    for f in fields:
        name = f.get("name", "")
        if not name:
            print(f"错误: 存在无 name 的字段", file=sys.stderr)
            sys.exit(1)
        lines = [name]  # 裸字段名
        opts = f.get("options") or []
        if isinstance(opts, str):
            opts = [o for o in opts.split("\n") if o.strip()]
        label = f.get("label", "")

        # RANGE（仅当有 range 且无 options/legal 时，二者互斥）
        nums = opt_numbers(f)
        legal = f.get("legal") or (nums if nums else None)
        rng = f.get("range") or auto_range(f, name, label)
        if rng and not legal:
            if isinstance(rng, (list, tuple)):
                rng_str = f"{rng[0]} {rng[1]}"
            else:
                rng_str = str(rng).replace('-', ' ')
            lines.append(f"  RANGE {rng_str}")

        # LEGAL 子块（选项/合法值，每个一行）；其后紧跟 COMMENT LEGAL USE 值标签
        if legal:
            lines.append("  LEGAL")
            for v in legal:
                lines.append(f"    {v}")
            lines.append("  END")
            if name in labels:
                lines.append(f"  COMMENT LEGAL USE label_{name.lower()}")

        # JUMPS 子块（显式 jumps + 自动"其他"跳转合并）
        jumps = auto_other_jumps(f, all_names)
        if jumps:
            lines.append("  JUMPS")
            for val, target in jumps.items():
                lines.append(f"    {val} {target}")
            lines.append("  END")

        # MUSTENTER（必填，连写；auto_required 推荐，显式 required 优先）
        required = f.get("required") if not args.auto_required else auto_required(f, name, label, opts)
        if required:
            lines.append("  MUSTENTER")

        # 无检查命令的字段不写入 chk（官方规范：if there are no Check commands, then nothing is written）
        if not (rng or legal or jumps or required):
            continue

        lines.append("END")  # 字段块结束（无缩进）
        blocks.append("\n".join(lines))

    parts = []
    if labelblock:
        parts.append(labelblock)
    parts.extend(blocks)
    content = "\n\n".join(parts) + "\n"
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
    print(f"✓ 已生成 {args.output}（{args.encoding}，{args.newline}，{len(blocks)} 个有规则字段块）")

if __name__ == "__main__":
    main()
