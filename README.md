# EpiData Toolkit

**流行病学调查表 → EpiData QES / CHK 生成、校验、编码修复工具链**

将 PDF / Word / Excel 格式的流行病学个案调查表（手足口病、禽流感、登革热等）转换为 EpiData 标准的 **QES 调查表文件** 与 **CHK 检查文件**，并提供完整的格式校验与编码修复能力。输出文件可直接在 EpiData EntryClient 中生成 REC 数据库进行数据录入。

## 功能特性

✅ **调查表 → QES**：支持扫描件 PDF（自动识别并转图 OCR）、Word、Excel、文本调查表
✅ **标准行格式**：`{变量名}问题文本掩码【n】选项`，符合 EpiData 3.1 中文版规范
✅ **CHK 检查文件**：标准格式生成（RANGE / LEGAL / JUMPS / MUSTENTER），自动"其他"跳转
✅ **一键生成**：一条命令同时产出 QES + CHK + 双格式查看版
✅ **多选 / 表格智能展开**：□A □B □C 每选项独立字段；表格按固定行数展开
✅ **GBK 兼容性预检**：生成前自动拦截上标（⁹）等 GBK 无法编码的字符
✅ **完整校验器**：字段格式 / 变量名唯一性 / 掩码合法性 / 编码可解码 / GBK 可编码性 / CRLF 行尾 / BOM
✅ **编码修复**：UTF-8 ↔ GBK、LF ↔ CRLF、BOM 增删一键处理

## 目录结构

```
epidata-toolkit/
├── SKILL.md                        # Skill 使用说明与工作流
├── scripts/
│   ├── qes_generator.py            # 字段定义 JSON → qes（含 GBK 预检）
│   ├── qes_validator.py            # qes 格式校验（9 项检查）
│   ├── fix_encoding.py             # 编码 / 行尾 / BOM 修复
│   ├── chk_generator.py            # 字段定义 JSON → chk（标准格式 + 自动"其他"跳转）
│   └── generate_all.py             # 一键生成：qes / txt / chk / chk检查txt
├── references/
│   ├── qes_format.md               # QES 格式完整规范（掩码、命名、展开规则）
│   └── chk_format.md               # CHK 标准格式规范 + 必填选取原则 + 校验清单
└── assets/
    └── template.qes                # 手足口病调查表标准格式模板
```

## 快速开始：一键生成全部文件

字段定义 JSON 就绪后，一条命令同时产出 4 个文件：

```bash
python3 scripts/generate_all.py survey.json -o 调查表
```

| 产出 | 编码 | 用途 |
|---|---|---|
| `调查表.qes` | GBK+CRLF+无BOM | EpiData 调查表 |
| `调查表.txt` | UTF-8 | qes 检查版（记事本查看） |
| `调查表.chk` | GBK+CRLF+无BOM | 检查规则（自动含"其他"跳转） |
| `调查表_chk检查.txt` | UTF-8 | chk 检查版 |

## 字段定义 JSON

```json
{
  "title": "附表1 流行病学调查表（禽流感病例）",
  "sections": [
    { "field": "FIRSTUNIT", "title": "一、病例的发现/报告情况" },
    { "field": "NAME", "title": "二、病例一般情况" }
  ],
  "fields": [
    { "name": "FIRSTUNIT", "type": "text",   "length": 15, "label": "1.病例的首次发现单位(具体到科室)" },
    { "name": "SEX",       "type": "number", "digits": 1,  "label": "2.性别", "options": ["【1】男", "【2】女"] },
    { "name": "NAME",      "type": "text",   "length": 4,  "label": "3.病例姓名" },
    { "name": "ONSETDT",   "type": "date",                  "label": "1.发病日期" },
    { "name": "FOUNDTM",   "type": "time",                  "label": "发现时间" },
    { "name": "OCCUPO",    "type": "text",   "length": 8,  "label": "【18】其他" }
  ],
  "required": ["FIRSTUNIT", "NAME", "SEX", "ONSETDT"],
  "ranges": { "MAXTEMP": [35.0, 42.0] },
  "jumps": { "OUTCOME": { "1": "OUTCOMEO" } }
}
```

### 字段类型与映射

| type | JSON 附加参数 | 生成掩码 | 说明 |
|---|---|---|---|
| number | digits: 1 | `#` | 单选/多选选项 |
| number | digits: 2 | `##` | 大选项集（>9 项） |
| number | digits: "2.1" | `##.#` | 带小数（体温、白细胞） |
| number | digits: 11 | `###########` | 联系电话（11 位手机号） |
| text | length: 4 | `________` | 文本（两_=一字，自动 ×2） |
| date | — | `<dd/mm/yyyy>` | 日期 |
| time | — | `##时##分` | 时间 |
| memo | length: 20 | 长下划线 | 小结/备注 |

## QES 行格式规范

字段行 = `{变量名}问题文本掩码【选项】`：变量名花括号包裹，问题文本在前、掩码在后**同行**，结尾补全角冒号 `：`；选项同行 `【1】男  【2】女`（双空格分隔）；章节标题为不以 `{` 开头的普通文本行。

```
附表1 流行病学调查表（禽流感病例）
一、病例的发现/报告情况
{FIRSTUNIT}1.病例的首次发现单位(具体到科室)：______________________________
{SEX}2.性别：#  【1】男  【2】女
{OCCUP}10.职业：##  【1】幼托儿童  【2】散居儿童  【17】医疗机构工作人员  【18】其他
{OCCUPO}【18】其他________________
{ONSETDT}1.发病日期：<dd/mm/yyyy>
{FOUNDTM}发现时间：##时##分
```

### 掩码速查

| 内容 | 写法 | 示例 |
|---|---|---|
| 数字 | `#`（多用 `##`） | `{SEX}性别：#  【1】男  【2】女` |
| 带小数 | `##.#` | `{MAXTEMP}最高体温：##.# ℃` |
| 文本 | `_`（两_=一字，偶数） | `{NAME}姓名：________` |
| 日期 | 6 种（见下） | `{ONSETDT}发病日期：<dd/mm/yyyy>` |
| 时间 | `##时##分` | `{FOUNDTM}发现时间：##时##分` |
| 联系电话 | `###########`（11 位） | `{TEL}联系电话：###########` |

### 日期仅支持 6 种

```
<dd/mm/yyyy>  <mm/dd/yyyy>  <yyyy/mm/dd>  <Today-dmy>  <Today-mdy>  <Today-ymd>
```

⚠️ 没有 `<hh:mm>`：具体时间用 `##时##分` 表达。

## CHK 标准格式规范

CHK 字段块结构（字段头 = 裸字段名，不写 TYPE；规则行缩进 2 空格；子块内容缩进 4；块末 `END` 无缩进）：

```
REPWAY
  RANGE 1 5
  LEGAL
    1
    4
    6
  END
  JUMPS
    5 REPWAYO
  END
  MUSTENTER
END
```

**规则要点**：

- `  RANGE 1 5`：数值范围，上下限空格分隔、无等号
- `LEGAL` 子块：只允许输入的选项值，每行一个（**LEGAL 与 RANGE 互斥**，选项字段走 LEGAL、纯数值走 RANGE）
- `JUMPS` 子块：`值 目标字段`（如选"其他"跳转到注明字段）
- `  MUSTENTER`：必须填写（连写无空格）
- 无规则的字段 = 裸字段名 + `END` 空块
- **自动"其他"跳转**：选项含"其他/其它"且存在注明字段（字段名+O）时自动生成跳转
- 未确认结构（TYPE/AUTOENTER/NOENTER/KEY/REPEAT/VERIFY 等）一律不生成

## 编码与兼容性（重要）

| 项目 | 要求 |
|---|---|
| 编码 | GBK/ANSI（EpiData 3.1 中文版），新版可 UTF-8 |
| 行尾 | CRLF（LF 生成 REC 会报错） |
| BOM | 无（有 BOM 首字段异常） |
| 特殊字符 | 上标（⁹ U+2079）GBK 不支持，用 ASCII：×10⁹/L → ×10^9/L；℃ 可用 |

## 常见问题

| 问题 | 现象 | 修复 |
|---|---|---|
| 行尾 LF | 生成 REC 报错 | `fix_encoding.py --newline crlf` |
| UTF-8 编码（老版） | 中文乱码 | `fix_encoding.py --encoding gbk` |
| 带 BOM | 首字段异常 | `--strip-bom` |
| 上标字符 ⁹ | GBK 编码报错 | 改 ASCII（×10^9/L） |
| 时间 `<hh:mm>` | 非法格式 | 改 `##时##分` |
| 下划线奇数 | 文本长度异常 | 两_=一字，补偶数 |
| 字段名重复 | 生成 REC 报错 | 改名重生成 |

## 校验清单

- 字段行格式 `{变量}问题文本掩码`
- 变量名合法（字母开头 ≤10 字符）且唯一
- 掩码合法：日期 6 种 / `##时##分` / 数字 / 偶数下划线
- 编码 GBK 或 UTF-8 可解码
- GBK 可编码性（无上标等非法字符）
- 行尾 CRLF、无 BOM
- CHK：字段块数与 QES 一致、RANGE 与 LEGAL 互斥、跳转目标全部存在、"其他"字段跳转全覆盖、必填字段不卡录入
- 对照原文完整性核对：字段数、章节、选项编号逐条一致

## 从调查表生成的工作流

1. 读取源文件：PDF 优先 `pdftotext -layout`；输出为空 = 扫描件 → `pdftoppm -png -r 150` 转图后视觉识别（注意水印）
2. 编写字段定义 JSON（命名：字母开头 ≤8 字符，语义化缩写，不重复）
3. 一键生成 + 校验 + 对照原文逐条核对
4. 交付：qes（GBK+CRLF）+ chk（GBK+CRLF）+ txt（UTF-8 检查版）

## License

MIT（可自行添加 LICENSE 文件后发布）
