---
name: epidata-toolkit
description: 处理 EpiData 流行病学调查表文件（qes/rec/chk）。当用户需要：将 PDF/Word/Excel/文本调查表转换为 EpiData qes 格式、根据字段定义生成 qes 文件、校验或修复 qes 文件、处理 GBK/UTF-8 编码与 CRLF/LF 行尾问题、生成 EpiData 数据录入文件时使用。
---

# EpiData QES 处理工具

## 快速开始：一键生成全部文件

字段定义 JSON 就绪后，一条命令同时产出 4 个文件（qes/txt/chk/chk检查txt），qes 与 chk 规则自动联动：

```bash
python3 scripts/generate_all.py survey.json -o 调查表
```

| 产出 | 编码 | 用途 |
|---|---|---|
| `调查表.qes` | GBK+CRLF+无BOM | EpiData 调查表 |
| `调查表.txt` | UTF-8 | qes 检查版（记事本查看） |
| `调查表.chk` | GBK+CRLF+无BOM | 检查规则（自动含"其他"跳转） |
| `调查表_chk检查.txt` | UTF-8 | chk 检查版 |

等价于依次运行 `qes_generator.py` → `chk_generator.py` → `fix_encoding.py` 转查看版。

## 概览

本 Skill 提供 EpiData 调查表文件（.qes）的生成、校验与编码修复能力。EpiData 是流行病学数据录入软件，qes 文件是其调查表结构定义文件（纯文本）。

## 工作流

### 1. 调查表 → qes 转换

**1.1 读取源文件**
- PDF：优先 `pdftotext -layout`；**输出为空 = 扫描件**（无文本层），改用 `pdftoppm -png -r 150` 转图片后用视觉读取逐页识别（注意水印干扰）。
- Word：按 word skill 读取；Excel：按 sheet skill 读取。

**1.2 生成字段定义（JSON）**
- **变量命名**：字母开头，仅含字母数字，≤8 字符，语义化缩写（NAME、MAXTEMP、ONSETDT）；不得重复；输出统一大写。
- **类型映射**（标准格式）：
  | 调查表内容 | 类型 | JSON | 输出掩码 |
  |---|---|---|---|
  | 单选/多选选项题 | number | `digits:1` | `#` |
  | 大选项集（>9项） | number | `digits:2` | `##` |
  | 带小数（体温/白细胞） | number | `digits:"2.1"` | `##.#` |
  | 文本 | text | `length:字数` | `_`×2（两_=一字） |
  | 日期 | date | — | `<dd/mm/yyyy>` |
  | 时间 | time | — | `##时##分`（无 `<hh:mm>`） |
  | 小结/备注 | memo | `length:字数` | 长下划线 |
- **联系电话 = 11 位数字**掩码 `###########`（type:"number", digits:11），不用文本下划线
- **多选（□A □B □C）展开**：每个选项一个独立字段（`#【1】有【2】无`），保证可多选录入；"其它"项加 `O` 后缀注明字段（label 写 `【n】其它`，不加冒号）。
- **表格展开**：按原表固定行数展开为多组字段，变量命名 `前缀+序号+列字母`（如就诊6次×8列：VISIT1U/VISIT1D/.../VISIT6O；禽类饲养3行：POUL1K...POUL3F；家庭成员5位：MEM1N...MEM5W）。
- **每个"其他____（注明）"选项**单独建文本字段，字段名加 `O` 后缀。
- **GBK 特殊字符陷阱**：上标字符（⁹ 等）GBK 无法编码，生成会报错；**℃ 可以**，`×10⁹/L` 要写成 `×10^9/L`。

**1.3 生成与交付**
1. `scripts/qes_generator.py <input.json> -o <output.qes>`（默认 GBK+CRLF）
2. `scripts/qes_validator.py <output.qes>` 校验
3. 交付 qes（GBK+CRLF，EpiData 用）+ txt（UTF-8，用户检查用，用 fix_encoding.py 转）
4. 生成后**对照原文逐条核对**：字段数、章节数、关键选项、选项编号，确保无遗漏

### qes 行格式规范（EpiData 标准）

- **字段行** = `{变量名}问题文本掩码[选项]`，变量名用**花括号 {}** 包裹
- 问题文本在前、输入掩码在后，同行连续书写，问题文本结尾补全角冒号 `：`
- **选项同行**：`【1】男  【2】女`（方括号编号、双空格分隔），不拆行
- **章节标题、说明文字** = 普通文本行（不以 `{` 开头，如 `一、病例一般情况`、`检查结果`）
- **注明字段**（`【n】其它____`）：变量名后直接写 `【n】其它` + 下划线，**不加冒号**
- 文本掩码用下划线（两个_=一字，必须偶数）；数字用 `#`（多用 `##`）；时间用 `##时##分`

示例：

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

### 2. qes 文件校验

运行 `scripts/qes_validator.py <file.qes>`，检查项：
- 字段行格式 `{变量名}问题文本掩码`
- 变量名合法（字母开头、≤10字符）且不重复
- 掩码合法：日期 6 种 / `##时##分` / `#`数字（可带小数点）/ 下划线（**必须偶数**）
- 非法 `<hh:mm>` 检出
- **GBK 可编码性**：全部字符 GBK 可编码（上标/生僻字会乱码报错）
- 编码可解码（UTF-8 或 GBK）、行尾 CRLF、无 BOM

### 3. 编码与行尾修复

运行 `scripts/fix_encoding.py <input> -o <output> --encoding gbk --crlf --strip-bom`，支持编码转换（UTF-8 ↔ GBK）、行尾转换（LF ↔ CRLF）、BOM 去除/添加。

### 4. 生成 chk 检查文件（数据质控）

字段 JSON 可附加 chk 规则（required/range/legal/jumps 等），运行：

```bash
python3 scripts/chk_generator.py survey.json -o 调查表.chk
```

**标准格式（用户锚定）**：字段头裸字段名（无花括号、不写 TYPE）；`  RANGE 1 5` 空格分隔；`LEGAL`/`JUMPS` 为子块（内容缩进4、`  END` 缩进2结束）；`  MUSTENTER` 连写；字段块以无缩进 `END` 收尾。**RANGE 与 LEGAL 互斥**（选项字段走 LEGAL，纯数值范围走 RANGE）。未确认结构（TYPE/AUTOENTER/NOENTER/KEY/REPEAT/VERIFY/BEFORE/AFTER）一律不生成。

**自动"其他"跳转**：字段选项含"其他/其它"且存在注明字段（字段名+O）时自动生成 JUMPS（选其他→注明栏），与显式 jumps 合并不覆盖。

**必填原则**：核心人口学/暴露/诊断/调查信息设 `required`；有"不知道"兜底的暴露字段放心必填；条件性字段不简单必填。

**生成后校验**：字段块数=qes 字段数；RANGE 与 LEGAL 互斥；JUMPS 目标全部存在；"其他"字段跳转全覆盖；MUSTENTER 逐一核对不卡录入。规则完整规范见 [references/chk_format.md](references/chk_format.md)。

### 5. 生成 rec 数据文件

.qes 是纯文本可直接生成；**.rec 数据文件必须用 EpiData 软件**（EntryClient 中由 qes 创建，自动加 ID 字段）。告知用户：打开 EpiData Entry → 选择 qes → 生成 rec，如报错优先检查编码（GBK）与行尾（CRLF）。

## 常见问题

| 问题 | 现象 | 修复 |
|---|---|---|
| 行尾 LF | 生成 rec 报错 | fix_encoding.py 转 CRLF |
| 编码 UTF-8（老版） | 中文乱码/报错 | 转 GBK |
| 带 UTF-8 BOM | 首字段异常 | 去 BOM |
| 上标字符（⁹） | GBK 编码报错 | 改 ASCII（×10^9/L） |
| 时间 `<hh:mm>` | 非法格式 | 改 `##时##分` |
| 下划线奇数 | 文本长度异常 | 两_=一字，补偶数 |
| 字段名重复 | 生成 rec 报错 | 改名重生成 |

## 参考资料

- 字段类型与掩码完整规范：见 [references/qes_format.md](references/qes_format.md)
- 示例模板：见 [assets/template.qes](assets/template.qes)（手足口病调查表标准格式）
