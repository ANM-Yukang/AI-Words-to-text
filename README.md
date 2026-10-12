# 转人话（v0.1 测试版）

你是否因为 AI 回复里满屏的 **加粗**、$公式$、一堆 `-` 和 `1.` 看得头大？
你是否想把一大段 AI 输出变成能一眼看懂的东西，却只能手动删符号、调格式？
你是否想把思维导图代码、表格贴到微信/QQ 里，结果对方看到的是一坨乱码？

## 它能干嘛

- **文字**：`$x^2$` 变 `x^2`，`\frac{1}{2}` 变 `(1)/(2)`，加粗、斜体、删除线的符号全去掉，只留文字；标题去掉 `#` 号，段落之间用空行排开
- **结构**：列表、脑图都变成带连接线的树（`├──`/`└──`/`│`，末枝自动用 `└──`，层级一眼看清）；表格变成对齐的字符表格（带 `|` 的、缺分隔行的、纯空格对齐的都可以），贴到任何聊天框都不会乱码
- **公式**：LaTeX 全量转普通文本——aligned/align 等对齐环境按行换行并按 `&` 分列，matrix 各变体按各自括号排成多行，cases 分段函数多行并闭合，极限、求和、积分、上下标、根号指数、化学式与物理量命令都能读；没包 `$` 的裸公式一样可以- **图表**：mermaid 全家族（mindmap、graph/flowchart、时序图、类图、状态图、ER 图、用户旅程、饼图、甘特图、提交图、象限图、需求图、时间线、桑基图、坐标图、块图、C4 共 17 类）转成树、连线或分条文本，有围栏没围栏都可以
- **清理**：隐形字符与双向标记、控制符一律清掉，Emoji 组合（家庭、职业、彩虹旗、国旗等）保持不拆散，不换行空格与全角空格归一为普通空格；HTML 实体、URL 百分号编码、JSON 转义在文本格式下还原成字符（代码格式不还原）
- **不动的部分**：代码块与「代码」格式原样保留，缩进和转义都按原样输出

## 怎么用

1. 装好 Python 3，命令行运行：

   ```
   python 转人话.py
   ```

2. 选语言：`1` 中文，`2` English（直接回车默认中文）
3. 选输入格式（直接回车默认 1）：

   - `1` 自动识别：混合内容，自动分块识别表格 / 脑图 / 公式`注意可能存在失误`
   - `2` Markdown 文档：标题、列表、表格、代码围栏按 Markdown 语义处理
   - `3` 纯文本：只去强调符号、转译公式，保留原有缩进
   - `4` 表格：整段按表格处理
   - `5` 思维导图：mermaid mindmap/graph，有围栏没围栏都行
   - `6` 公式：整段按 LaTeX 处理，含没包 `$` 的裸公式
   - `7` 代码：原样保留，只清隐形字符

4. 粘贴你的内容，最后单独打一行 `::end` 回车（Windows 也可以 Ctrl+Z 回车）

## 说明

- 单文件，只用 Python 自带库，不用装任何依赖。
- 详细支持范围（LaTeX 命令与环境、mermaid 图类型、实体数量等）见同目录 `覆盖清单.md`。

---

# Zhuan Renhua (AI Text → Plain Text)  v0.1 test build

Tired of AI replies stuffed with **bold**, $math$, and endless `-` / `1.` markers?
Tired of manually stripping symbols just to read or forward something?
Tired of pasting a "mindmap" into chat only to send your friend a wall of code?

## What it does

- **Text**: `$x^2$` → `x^2`, `\frac{1}{2}` → `(1)/(2)`; bold/italic/strikethrough markers are stripped, heading `#` marks dropped, and paragraphs are re-laid-out for easy reading
- **Structure**: lists and mindmaps become connected trees (`├──` / `└──` / `│`, last branch auto-detected); tables (piped, separator-less or space-aligned) become aligned character tables that survive any chat box
- **Formulas**: full LaTeX to plain text — aligned/align environments break into lines and split columns on `&`, every matrix variant gets its own delimiters, cases blocks close properly, and limits, sums, integrals, scripts, root indices, chemistry and physics-quantity commands all read as text; bare formulas without `$` work too
- **Diagrams**: the whole mermaid family (mindmap, graph/flowchart, sequence, class, state, ER, journey, pie, gantt, gitGraph, quadrant, requirement, timeline, sankey, xychart, block, C4 — 17 kinds) becomes trees, edges or numbered text, fenced or unfenced
- **Cleanup**: invisible and bidi marks plus control characters are removed, emoji sequences (family, professions, rainbow flag, country flags) stay intact, and no-break / full-width spaces are normalized; HTML entities, URL percent-encoding and JSON escapes are decoded in text formats (not in code)
- **Left untouched**: code blocks and the code format keep their original bytes, indentation and escapes

## How to use

1. Requires Python 3. Run:

   ```
   python 转人话.py
   ```

2. Pick a language: `1` Chinese, `2` English (Enter = Chinese)
3. Pick an input format (Enter = 1):

   - `1` Auto: mixed content, detects tables / mindmaps / formulas block by block
   - `2` Markdown: headings, lists, tables and code fences handled as Markdown
   - `3` Plain text: only emphasis markers and formulas are converted, indentation kept
   - `4` Table: the whole input is treated as one table
   - `5` Mindmap: mermaid mindmap/graph, fenced or not
   - `6` Formula: the whole input is treated as LaTeX, including bare formulas
   - `7` Code: kept as-is, only invisible characters removed

4. Paste your content, then type a line with just `::end` and press Enter (Ctrl+Z works too on Windows)

## Notes

- Single file. Standard library only, no dependencies.
- Full support list (LaTeX commands and environments, mermaid types, entity counts) is in `覆盖清单.md` in the same folder.
