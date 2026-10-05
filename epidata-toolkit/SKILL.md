---
name: epidata-toolkit
description: 处理 EpiData 流行病学调查表文件（qes/rec/chk）。当用户需要：将 PDF/Word/Excel/文本调查表转换为 EpiData qes 格式、根据字段定义生成 qes 文件、校验或修复 qes 文件、处理 GBK/UTF-8 编码与 CRLF/LF 行尾问题、生成 EpiData 数据录入文件（chk 检查文件）、双录入 rec 比对与数据质量检查时使用。
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

## 全流程路线（0 → rec → 比对）

```
调查表(PDF/Word/扫描件) → 字段JSON → 一键生成 qes/txt/chk → 校验
→ [EpiData EntryClient: 打开 qes → 生成 rec 数据库] → 双录入(两人各录一份)
→ rec_compare 比对 → 差异报告 → 按差异回查修正 → 再比对至 100% 一致
```

- 第 1–3 步（生成/校验/修复）见下文 §1–§3，AI 自动完成
- 第 4 步（EpiData 建库与录入）必须在 EpiData EntryClient 软件中操作，见 §5
- 第 5 步（双录入比对）见 §5，输入只需两份 .rec

## 概览

本 Skill 提供 EpiData 调查表文件（.qes）的生成、校验与编码修复能力。EpiData 是流行病学数据录入软件，qes 文件是其调查表结构定义文件（纯文本）。

## 工作流

### 1. 调查表 → qes 转换

**1.1 读取源文件**
- PDF：优先 `pdftotext -layout`；**输出为空 = 扫描件**（无文本层），改用 `pdftoppm -png -r 150` 转图片后用视觉读取逐页识别（注意水印干扰）。
- Word：按 word skill 读取；Excel：按 sheet skill 读取。

**1.2 生成字段定义（JSON）**
- **变量命名**：字母开头，仅含字母数字，≤10 字符（与校验器一致），语义化缩写（NAME、MAXTEMP、ONSETDT）；不得重复；输出统一大写。
- **类型映射**（标准格式）：
  | 调查表内容 | 类型 | JSON | 输出掩码 |
  |---|---|---|---|
  | 单选/多选选项题 | number | `digits:1` | `#` |
  | 大选项集（>9项） | number | `digits:2` | `##` |
  | 带小数（体温/白细胞） | number | `digits:"2.1"` | `##.#` |
  | 文本 | text | `length:字数` | `_`×2（两_=一字） |
  | 身份证号 | text | `length:18, ascii:true` | `__________________`（18个下划线，ASCII 1字符=1列；末位大写 X 可录） |
  | 传真号码 | text | `length:12, ascii:true` | `____________`（12个下划线，容纳"区号-号码"如 `010-12345678`，横线可录；不用 number） |
  | 日期 | date | — | `<yyyy/mm/dd>` |
  | 时间 | time | — | `##时##分`（无 `<hh:mm>`） |
  | 小结/备注 | memo | `length:字数` | 长下划线 |
- **联系电话 = 11 位数字**掩码 `###########`（type:"number", digits:11），不用文本下划线；label 含"电话/手机"自动匹配 11 位
- **身份证号 = 文本 18 个下划线**（type:"text", length:18, ascii:true）——ASCII 1 字符 = 1 列，末位大写 X 可正常录入（2026-10-05 用户确认：EpiData 数字字段录不了 X，身份证不用 number）；E-mail 等 ASCII 文本同理可用 ascii:true
- **传真号码 = 文本 12 个下划线**（type:"text", length:12, ascii:true）——大陆传真 = 区号(3-4位) + 本地号码(7-8位)，常带横线如 `010-12345678`（11-12 字符），横线需文本可录，不用 number
- **多选（□A □B □C）展开**：每个选项一个独立字段（`#【1】有【2】无`），保证可多选录入；"其它"项加 `O` 后缀注明字段（label 写 `【n】其它`，不加冒号）。
- **表格展开**：按原表固定行数展开为多组字段，变量命名 `前缀+序号+列字母`（如就诊6次×8列：VISIT1U/VISIT1D/.../VISIT6O；禽类饲养3行：POUL1K...POUL3F；家庭成员5位：MEM1N...MEM5W）。
- **"其他/其它____（注明）"自动补齐**：字段选项含"其他/其它"时，生成器自动追加注明字段 `字段名+O`（文本，label 取选项原文如 `【18】其他`，不加冒号），无需手工配置；若 JSON 已显式定义同源注明字段（`name+O` 或 `name[:-1]+O`，兼容 HANDWASO 式简化命名）则跳过，不重复生成。
- **掩码位数自动匹配**：number 字段未显式 `digits` 时，按选项编号最大位数自动设置（选项到【10】以上自动用 `##`），不会截断录入
- **日期格式自动推断**：date 字段未显式 `date_format` 时，按 label 中"年 月 日/日 月 年/月 日 年"连续提示自动推断 `<yyyy/mm/dd>`/`<dd/mm/yyyy>`/`<mm/dd/yyyy>`；无提示默认 `<yyyy/mm/dd>`
- **上标字符自动替换**：GBK 不支持的字符自动替换（`⁹→^9`、下标数字→数字），替换后仍不可编码才报错；GBK 原生支持 ℃±×÷≤≥μ 与罗马数字 Ⅰ-Ⅻ（对照见 references/gbk_chars.md）
- **label 符号自动转中文**：问题文本中的数学/范围符号生成时自动替换（`>=→大于等于`、`<=→小于等于`、`>`→大于、`<`→小于、`=`→等于），避免 qes 行中 `<` `>` 干扰 EpiData 解析（掩码标记）、`=` 影响显示；**`-` 仅在两侧都是数字（数值范围如 `3-5岁`→`3至5岁`）时转"至"，单词连字符（E-mail、X-ray）保留**；日期掩码 `<dd/mm/yyyy>` 等不受影响

**1.3 生成与交付**
1. `scripts/qes_generator.py <input.json> -o <output.qes>`（默认 GBK+CRLF；自动：掩码位数匹配/日期格式推断/上标替换）
2. `scripts/qes_validator.py <output.qes>` 校验
3. `scripts/generate_all.py <input.json> -o <基名>` 一键产出 qes + txt + chk + chk检查版；多份调查表用 `scripts/batch_generate.py <json目录> -o <输出目录>` 批量生成
4. 交付 qes（GBK+CRLF，EpiData 用）+ txt（UTF-8，用户检查用，用 fix_encoding.py 转）
5. 生成后**对照原文逐条核对**：字段数、章节数、关键选项、选项编号，确保无遗漏

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
{ONSETDT}1.发病日期：<yyyy/mm/dd>
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

**标准格式（用户锚定）**：字段头裸字段名（无花括号、不写 TYPE）；`  RANGE 1 5` 空格分隔；`LEGAL`/`JUMPS` 为子块（内容缩进4、`  END` 缩进2结束）；`  MUSTENTER` 连写；字段块以无缩进 `END` 收尾。**RANGE 与 LEGAL 互斥**（选项字段走 LEGAL，纯数值范围走 RANGE）。**无检查命令的字段不写入 chk**（官方规范：if there are no Check commands, then nothing is written）。未确认结构（TYPE/AUTOENTER/NOENTER/KEY/REPEAT/VERIFY/BEFORE/AFTER）一律不生成。

**LABELBLOCK 值标签（EpiData 3.1 真实格式，2026-10-05 确认）**：含编号选项的字段自动在 chk 文件头生成值标签块 + 字段块内关联：
```
LABELBLOCK
  LABEL label_sex
    1  男
    2  女
  END
END
SEX
  LEGAL
    1
    2
  END
  COMMENT LEGAL USE label_sex   ← LEGAL END 后紧跟
  MUSTENTER
END
```
- 标签名规则：`label_` + 字段名小写（label_sex/label_marital）；标签文本取选项【n】后的原文，编号一一对应
- 字段 JSON 显式 `"labelblock": false` 可关闭（长文本选项如 EDU 式字段不生成标签）
- LABELBLOCK 仅在至少一个字段需要标签时输出

**自动规则（默认开启）**：
- "其他"补齐：字段选项含"其他/其它"时 qes 自动生成注明字段 `字段名+O`，chk 自动 JUMPS（其他编号 → 注明字段），含"其他"字段 100% 覆盖跳转
- RANGE 自动推断：无 options 的数值字段按字段名/标签命中保守表自动生成（年龄 0-120、体温 30-45），显式 range 优先
- 必填自动推荐：显式 `required` 优先；核心信息字段（精确匹配 NAME/SEX/AGE/OCCUP/ONSETDT/OUTCOME/ADDRESS/MOBILE/TEL 等）、标签命中核心关键词、或含"不知道/不详"兜底选项的字段自动 MUSTENTER；`--no-auto-required` 可关闭

**必填原则**：核心人口学/暴露/诊断/调查信息设 `required`；有"不知道"兜底的暴露字段放心必填；条件性字段不简单必填。

**生成后校验**：有规则字段块数 ≤ qes 字段数（无规则不写）；块全部含规则（无空块）；RANGE 与 LEGAL 互斥；JUMPS 目标全部存在；"其他"字段跳转全覆盖；MUSTENTER 逐一核对不卡录入。规则完整规范见 [references/chk_format.md](references/chk_format.md)。

### 5. rec 数据文件与结构校验、双录入比对

**.rec 数据文件必须用 EpiData 软件生成**（EntryClient 中由 qes 创建，自动加 ID 字段）：打开 EpiData Entry → 选择 qes → 生成 rec，如报错优先检查编码（GBK）与行尾（CRLF）。

**rec↔qes 结构校验**（生成 rec 后必做，防字段错位/漏项）：
```bash
python3 scripts/rec_check.py 调查表.qes 数据.rec [-o 报告.txt]
```
- 比对字段数量/名称/顺序（自动过滤 rec 的 LABEL 标题字段与自动 ID 字段）
- **chk 与 rec 必须由同一份 qes 配套生成**：rec 字段名若与 qes 不一致（如 FOUNDTM1 vs FOUNDTM），EpiData 会拒绝加载 chk（表现为"扫描不到 chk"）
- 退出码 0=一致、2=不一致

**双录入比对**（EpiData 数据质量核心环节：两人各录一遍，比对不一致处回查原始问卷）：
```bash
python3 scripts/rec_compare.py 录入1.rec 录入2.rec -o 差异报告.txt
```

- **自包含解析**：rec 内嵌字段定义（首行字段数/记录数 + 每字段名称/类型/宽度），无需外部 JSON
- 先比对字段定义（名称/顺序/宽度），不一致报警（退出码 2）；一致后按记录号逐字段比对
- 输出一致率与差异明细（记录号 + 字段名 + 两值）；退出码 0=一致、1=有差异
- 空数据库（未录入）提示后正常完成
- rec 真实格式（已实测校准）与宽度速查见 [references/rec_format.md](references/rec_format.md)

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
