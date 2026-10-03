# EpiData Toolkit

**流行病学调查表 → EpiData QES / CHK / REC 全流程工具链**

把 PDF / Word / 扫描件形式的流行病学个案调查表（手足口病、禽流感、肺结核等）转换为 EpiData 标准文件，并在录入后完成双录入比对质检。

## 功能特性

- ✅ 调查表 → QES：扫描件自动转图识别、多选/表格智能展开、标准行格式
- ✅ CHK 检查文件：RANGE / LEGAL / JUMPS / MUSTENTER，自动「其他」跳转
- ✅ 一键生成：一条命令产出 qes + txt + chk + 检查版共 4 个文件
- ✅ 完整校验：字段格式 / 变量名唯一 / 掩码合法性 / GBK 编码 / 行尾 / BOM
- ✅ 编码修复：UTF-8 ↔ GBK、LF ↔ CRLF、BOM 增删
- ✅ REC 双录入比对：自包含解析，逐字段比对输出差异报告

## 快速开始

字段定义 JSON 就绪后（可交给 AI 从调查表自动生成）：

```bash
python3 scripts/generate_all.py survey.json -o 调查表
```

| 产出 | 编码 | 用途 |
|---|---|---|
| `调查表.qes` | GBK+CRLF | EpiData 调查表 |
| `调查表.txt` | UTF-8 | 检查版（记事本打开） |
| `调查表.chk` | GBK+CRLF | 检查规则 |
| `调查表_chk检查.txt` | UTF-8 | chk 检查版 |

EpiData EntryClient 打开 qes 生成 rec 数据库 → 双人各录入一份 → 比对：

```bash
python3 scripts/rec_compare.py 录入1.rec 录入2.rec -o 差异报告.txt
```

## 目录结构

```
epidata-toolkit/
├── SKILL.md                     # 完整使用说明与工作流
├── scripts/
│   ├── generate_all.py          # 一键生成 qes/txt/chk（推荐入口）
│   ├── qes_generator.py         # 字段 JSON → qes
│   ├── qes_validator.py         # qes 校验（9 项）
│   ├── chk_generator.py         # 字段 JSON → chk
│   ├── fix_encoding.py          # 编码/行尾/BOM 修复
│   └── rec_compare.py           # rec 双录入比对
├── references/
│   ├── qes_format.md            # QES 行格式与掩码规范
│   ├── chk_format.md            # CHK 标准格式与规则
│   └── rec_format.md            # REC 真实格式与比对说明
└── assets/
    └── template.qes             # 标准格式模板
```

## 编码要求（重要）

- qes / chk 用 **GBK + CRLF + 无 BOM**（EpiData 3.1 中文版）；LF 或 UTF-8 生成 rec 会报错
- 上标字符（⁹）GBK 不支持，需写为 ASCII（×10^9/L）
- 详细格式规范见 `references/` 三个文档

## 实测验证

- 禽流感调查表 382 字段（qes + chk + rec 结构解析）
- 肺结核调查表 170 字段（rec 结构解析）
- 双录入比对：差异定位、一致率统计、退出码 0/1/2

## License

MIT
