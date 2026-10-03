# EpiData Toolkit

**流行病学调查表 → EpiData QES / CHK / REC 全流程工具链**

把 PDF / Word / 扫描件形式的流行病学个案调查表（手足口病、禽流感、肺结核等）转换为 EpiData 标准文件，并在录入后完成双录入比对质检。

## 功能特性

- ✅ 调查表 → QES：扫描件自动转图识别、多选/表格智能展开、标准行格式
- ✅ CHK 检查文件：RANGE / LEGAL / JUMPS / MUSTENTER，自动「其他」跳转
- ✅ 「其他」注明字段自动补齐：含"其他/其它"选项自动生成 `字段名+O` 注明栏并联动跳转，无漏项
- ✅ 智能推断：掩码位数自动匹配（选项≥10 自动 `##`）、日期格式自动推断、RANGE 自动推断（年龄/体温）、必填字段自动推荐
- ✅ 上标自动替换：⁹→^9 等 GBK 不支持字符自动改写（℃±×Ⅳ 等原生支持）
- ✅ 一键生成：一条命令产出 qes + txt + chk + 检查版共 4 个文件；支持目录批处理
- ✅ 完整校验：字段格式 / 变量名唯一 / 掩码合法性 / GBK 编码 / 行尾 / BOM
- ✅ rec↔qes 结构校验：比对字段数量/名称/顺序，防错位漏项
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
│   ├── batch_generate.py        # 批处理：目录下所有 JSON 批量生成
│   ├── qes_generator.py         # 字段 JSON → qes（自动掩码/日期/上标）
│   ├── qes_validator.py         # qes 校验（9 项）
│   ├── chk_generator.py         # 字段 JSON → chk（自动 RANGE/必填/跳转）
│   ├── rec_check.py             # rec↔qes 结构校验
│   ├── rec_compare.py           # rec 双录入比对
│   └── fix_encoding.py          # 编码/行尾/BOM 修复
├── references/
│   ├── qes_format.md            # QES 行格式与掩码规范
│   ├── chk_format.md            # CHK 标准格式与规则
│   ├── rec_format.md            # REC 真实格式与比对说明
│   └── gbk_chars.md             # GBK 字符集实测对照表
└── assets/
    └── template.qes             # 标准格式模板
```

## 编码要求（重要）

- qes / chk 用 **GBK + CRLF + 无 BOM**（EpiData 3.1 中文版）；LF 或 UTF-8 生成 rec 会报错
- 上标字符（⁹）GBK 不支持，需写为 ASCII（×10^9/L）
- 详细格式规范见 `references/` 三个文档

## 实测验证

- 禽流感调查表 389 字段（含自动补齐的「其他」注明字段，qes + chk + rec 结构解析）
- 肺结核调查表 170 字段（rec 结构解析）
- 双录入比对：差异定位、一致率统计、退出码 0/1/2

## 常见问题与报错排查

| 现象 | 原因 | 解决 |
|---|---|---|
| EpiData 打开 qes 报错 / 乱码 | qes 是 UTF-8 而非 GBK | 用 `fix_encoding.py --encoding gbk --crlf --strip-bom` 转码 |
| 生成 rec 报"字段名非法" | 字段名超过 10 字符 / 重复 | 检查 JSON 字段名（字母开头、≤10、不重复），重新生成 |
| 生成 rec 报错，无明确提示 | 行尾是 LF 而非 CRLF | `fix_encoding.py --crlf` 转行尾 |
| 录入选"其他"不跳注明栏 | 注明字段缺失或未生成跳转 | 检查含"其他"选项字段：生成器自动补齐 `字段名+O` 并自动 JUMPS |
| check 规则不生效 / "扫描不到 chk" | ① chk 与 rec 不同名或不同目录；② **chk 与 rec 字段不一致**（chk 必须由生成 rec 的那份 qes 配套生成，混用不同版本的 qes/chk 会被 EpiData 拒绝） | 同名同目录放 chk；用 `generate_all.py` 从同一 JSON 生成 qes+chk，并用该 qes 建 rec |
| 录入时 RANGE 拦正常值 | RANGE 过窄（如年龄 0-120 拦 121+） | 检查字段 JSON range，或依赖自动推断（年龄 0-120、体温 30-45） |
| 文本录不满 | 下划线掩码宽度不足 | 文本字段 `length` 为中文字数，两个 `_`=一字，检查 JSON length |
| 上标/特殊符号乱码 | ⁹Ⅳ 等 GBK 无法编码 | 生成器已自动替换（⁹→^9）；替换后仍报错请手动改为 GBK 支持写法 |

更多格式细节见 `references/` 三个文档。

## License

MIT
