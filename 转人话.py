# -*- coding: utf-8 -*-
"""转人话：把 AI 生成的文本转成易读的人话或框架结构。"""
import base64
import html
import re
import sys
import unicodedata

END_MARK = "::end"
VERSION = "v0.1"
LANG = "zh"
FMT = 1
# 字符清洗统计
STATS = {"invisible": 0, "control": 0, "space": 0, "entity": 0}
# 隐形字符与双向标记
INVISIBLE = frozenset("\u200b\ufeff\u2060\ufffc\u200e\u200f"
                      "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
# 零宽连接符与非连接符，仅夹在字母或 emoji 序列中时保留
JOINER = frozenset("\u200c\u200d")
# 需要归一为普通空格的空白字符
NORMALIZE_SPACE = frozenset("\u00a0\u202f\u3000")
# 裸环境占位符字符，仅转换期间使用，输出前清除
ENV_MARK = "\ue000"
ENV_MARK_END = "\ue001"

# 中英文文案
T = {
    "zh": {
        "title": "转人话 · AI 文本易读转换工具",
        "lang_menu": "请选择界面语言：1=中文  2=English  （直接回车默认中文）",
        "fmt_menu": "请选择输入格式：1=自动识别（混合内容，分块识别表格/脑图/公式）  2=Markdown 文档（标题/列表/表格/围栏）  3=纯文本（只去强调与转公式，保留缩进）  4=表格（整段按表格处理）  5=思维导图（mermaid mindmap/graph，有无围栏均可）  6=公式（LaTeX，含没包 $ 的裸公式）  7=代码（原样保留，只清隐形字符）  （直接回车默认 1）",
        "fmt_1": "已选择：自动识别",
        "fmt_2": "已选择：Markdown 文档",
        "fmt_3": "已选择：纯文本",
        "fmt_4": "已选择：表格",
        "fmt_5": "已选择：思维导图",
        "fmt_6": "已选择：公式",
        "fmt_7": "已选择：代码",
        "paste_hint": "请粘贴内容，以单独一行 ::end 或 Ctrl+Z(Windows)/Ctrl+D(Unix) 结束，然后回车：",
        "empty_in": "没有检测到任何内容，请重新运行并粘贴要处理的文本。",
        "warn_head": "※ 提示",
        "code_note": "【代码块，内容原样保留】",
        "code_note_lang": "【代码块 {lang}，内容原样保留】",
        "done": "处理完成，可关闭本窗口或重新运行处理下一段内容。",
        "unclosed_code": "检测到代码块没有正确闭合（缺少结尾 ```），代码部分已按原样保留。",
        "unclosed_formula": "检测到公式或括号可能没有闭合（有残留的 $ 或 \\( ），已按原文保留。",
        "bad_lang": "输入无效，已默认使用中文。",
        "bad_fmt": "输入无效，已默认使用自动识别。",
        "no_tree": "未识别到 mindmap/graph 语法，已按原文保留。",
        "no_table": "未识别到多列结构，已按单列输出。",
        "cleanup": "字符清洗：隐形/双向字符 {invisible} 个，控制字符 {control} 个，空白归一 {space} 处，实体/转义还原 {entity} 处。",
        "err_generic": "处理过程中出现意外问题：{err}。已安全结束，未输出堆栈。",
    },
    "en": {
        "title": "Humanizer · Readable Converter for AI Text",
        "lang_menu": "Choose language: 1=中文  2=English  (Enter defaults to Chinese)",
        "fmt_menu": "Choose input format: 1=Auto (mixed; blocks of tables/mindmaps/formulas)  2=Markdown (headings/lists/tables/fences)  3=Plain text (emphasis + formulas only)  4=Table (whole input)  5=Mindmap (mermaid mindmap/graph, fenced or not)  6=Formula (LaTeX, incl. bare)  7=Code (kept as-is, invisibles cleaned)  (Enter defaults to 1)",
        "fmt_1": "Selected: auto-detect",
        "fmt_2": "Selected: Markdown",
        "fmt_3": "Selected: plain text",
        "fmt_4": "Selected: table",
        "fmt_5": "Selected: mindmap",
        "fmt_6": "Selected: formula",
        "fmt_7": "Selected: code",
        "paste_hint": "Paste your content, end with a line '::end' or Ctrl+Z/Ctrl+D, then press Enter:",
        "empty_in": "No input detected. Please rerun and paste the text to convert.",
        "warn_head": "※ Notes",
        "code_note": "[Code block, kept as-is]",
        "code_note_lang": "[Code block {lang}, kept as-is]",
        "done": "Done. You can close this window or rerun for the next piece.",
        "unclosed_code": "A code block seems unclosed (missing closing ```); code kept as-is.",
        "unclosed_formula": "A formula/bracket may be unclosed (leftover $ or \\(); original text kept.",
        "bad_lang": "Invalid input; defaulting to Chinese.",
        "bad_fmt": "Invalid input; defaulting to auto-detect.",
        "no_tree": "No mindmap/graph syntax recognized; original text kept.",
        "no_table": "No multi-column structure recognized; output as a single column.",
        "cleanup": "Cleanup: {invisible} invisible/bidi chars, {control} control chars, {space} spaces normalized, {entity} entities/escapes restored.",
        "err_generic": "Unexpected problem: {err}. Ended safely without a stack trace.",
    },
}


def t(key):
    return T[LANG][key]


def code_note(label=""):
    """代码块提示，保留围栏的语言标签。"""
    return t("code_note_lang").format(lang=label) if label else t("code_note")


def w(text):
    """显示宽度：东亚全角记 2。"""
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in "WF" else 1
    return total


def reconfigure_stdio():
    """重配标准流为 UTF-8，避免管道与控制台中文崩溃。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


SEP_LINE_RE = re.compile(r"^[─━═\-=*_·]{3,}[ \t]*$")


def tighten(text):
    """压缩多余空行与重复分隔线，保留首行缩进。"""
    out = []
    for line in text.split("\n"):
        if SEP_LINE_RE.match(line):
            if out and SEP_LINE_RE.match(out[-1]):
                continue
            out.append(line.rstrip())
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n")


# ---------------- 字符清洗（所有格式始终生效） ----------------

# HTML5 命名实体表（标准库数据），数字实体由 html.unescape 处理
ENTITIES = html.entities.html5
ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});")
PCT_RE = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
# 公式段（实体与转义还原要绕开）：$$ 块可跨行，裸环境整块保护
MATH_SPAN = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)"
                       r"|\\begin\{([A-Za-z*]+)\}.*?\\end\{\1\}", re.S)
# 代理对、\U/\u/\x、八进制与常见简单转义（单字母转义后不能再跟字母，避免吃掉 \frac 这类命令）
ESC_RE = re.compile(r"\\u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})"
                    r"|\\(U[0-9A-Fa-f]{8}|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2}|[0-7]{1,3}"
                    r"|(?:[ntrabfv\\\"'])(?![A-Za-z]))")
SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "a": "\x07", "b": "\x08",
              "f": "\x0c", "v": "\x0b", "\\": "\\", '"': '"', "'": "'"}


def is_emoji_char(ch):
    """emoji 本体、肤色修饰或变体选择符；空串按非 emoji 处理。"""
    return bool(ch) and (unicodedata.category(ch) in ("So", "Sk") or ch == "\ufe0f")


def clean_chars(text):
    """删除隐形与控制字符、归一空白，保护 emoji 组合。"""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch in JOINER:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if (is_emoji_char(prev) and is_emoji_char(nxt)) \
                    or (bool(prev) and bool(nxt) and prev.isalnum() and nxt.isalnum()):
                out.append(ch)
            else:
                STATS["invisible"] += 1
            continue
        if ch in INVISIBLE:
            STATS["invisible"] += 1
            continue
        if ch in "\u2028\u2029":
            # 行/段分隔符按换行处理，避免把两行黏在一起
            STATS["control"] += 1
            out.append("\n")
            continue
        code = ord(ch)
        if (code < 0x20 and ch not in "\n\t") or 0x7f <= code <= 0x9f:
            STATS["control"] += 1
            continue
        if ch in NORMALIZE_SPACE:
            STATS["space"] += 1
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def decode_escapes(text):
    """还原 HTML 实体、URL 百分号编码与 Python/JSON 风格转义。"""
    def ent(m):
        raw = m.group(0)
        if raw[1] == "#":
            new = html.unescape(raw)
        else:
            # 带分号的名字必须整名命中 HTML5 表，缺失则原样保留
            new = ENTITIES.get(raw[1:], raw)
        if new != raw:
            STATS["entity"] += 1
        return new

    def pct(m):
        try:
            new = bytes(int(x, 16) for x in re.findall(r"%([0-9A-Fa-f]{2})", m.group(0))).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return m.group(0)
        if new != m.group(0):
            STATS["entity"] += 1
        return new

    def esc(m):
        STATS["entity"] += 1
        if m.group(1):
            hi, lo = int(m.group(1), 16), int(m.group(2), 16)
            return chr(0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00))
        body = m.group(3)
        if body[0] in "Uux":
            return chr(int(body[1:], 16))
        if body[0] in "01234567":
            return chr(int(body, 8))
        return SIMPLE_ESC[body]

    return ESC_RE.sub(esc, PCT_RE.sub(pct, ENTITY_RE.sub(ent, text)))


# ANSI 控制序列：CSI（颜色/光标）、OSC（超链接等）与两字符转义
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-_]")
# 候选 Base64 片段
B64_RE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{16,}={0,2}(?![A-Za-z0-9+/=])")
HEX_RE = re.compile(r"[0-9a-fA-F]+")
CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f\uac00-\ud7af]")


def strip_ansi(text):
    """剥除 ANSI 控制序列，统计次数。"""
    def repl(m):
        STATS["control"] += 1
        return ""
    return ANSI_RE.sub(repl, text)


def restore_b64(text):
    """还原明显的 Base64 片段：长度合法、UTF-8 成功、含中日韩文字。"""
    def repl(m):
        s = m.group(0)
        body = s.rstrip("=")
        if len(body) % 4 == 1 or HEX_RE.fullmatch(body):
            return s
        try:
            new = base64.b64decode(body + "=" * (-len(body) % 4)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return s
        if not CJK_RE.search(new) or any(ord(c) < 0x20 and c not in "\n\t" for c in new):
            return s
        STATS["entity"] += 1
        return new
    return B64_RE.sub(repl, text)


def decode_outside_math(line):
    """只还原公式段之外的实体、转义与 Base64，避免破坏 LaTeX 的反斜杠。"""
    def conv(seg):
        return restore_b64(decode_escapes(seg))

    out = []
    pos = 0
    for m in MATH_SPAN.finditer(line):
        out.append(conv(line[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(conv(line[pos:]))
    return "".join(out)


def clean_text(text, decode=True):
    """按围栏分块清洗；代码块内不还原，公式段跳过还原。"""
    out = []
    fenced = False
    buf = []

    def flush():
        """把累积的非代码行作为一个整块清洗。"""
        if not buf:
            return None
        block = "\n".join(buf)
        del buf[:]
        # ANSI 序列先剥除，避免只剩残留参数
        block = strip_ansi(block)
        if decode and not fenced:
            # 还原后可能带入隐形字符或特殊空白，再清洗一遍
            block = clean_chars(strip_ansi(decode_outside_math(block)))
        else:
            block = clean_chars(block)
        return block

    for line in text.split("\n"):
        if line.strip().startswith("```"):
            chunk = flush()
            if chunk is not None:
                out.append(chunk)
            fenced = not fenced
            out.append(clean_chars(line))
            continue
        buf.append(line)
    chunk = flush()
    if chunk is not None:
        out.append(chunk)
    return "\n".join(out)


# ---------------- Markdown 结构 ----------------

MD_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"([^\"]*)\")?\s*\)")
MD_AUTO = re.compile(r"<(?:((?:https?|ftp|mailto):[^>\s]+)|([\w.+-]+@[\w-]+\.[\w.]+))>")
MD_BR = re.compile(r"<br\s*/?>", re.I)
HTML_TAGS = ("b|i|u|s|em|strong|code|span|div|p|sub|sup|small|mark|del|ins|a|h[1-6]|li|ul|ol"
             "|table|tr|td|th|pre|blockquote|img|font|center|kbd|var|samp|abbr|cite|q|time"
             "|ruby|rt|hr|tbody|thead|figure|figcaption")
MD_TAG = re.compile(r"</?(?:%s)(?:\s[^>]*)?/?>" % HTML_TAGS, re.I)
MD_FOOT = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
MD_TASK = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.*)$")
MD_QUOTE = re.compile(r"^(\s*)(>+)\s?(.*)$")
MD_HR = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
MD_DEF = re.compile(r"^:\s+(.*)$")
MD_SUB_MARK = re.compile(r"~([0-9A-Za-z+\-=()]{1,4})~")
MD_SUP_MARK = re.compile(r"\^([0-9A-Za-z+\-=()]{1,4})\^")
SUPER_MAP = dict(zip("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾"))
SUPER_MAP.update({"n": "ⁿ", "i": "ⁱ"})
SUB_MAP = dict(zip("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"))
SUB_MAP.update(dict(zip("aehijklmnoprstuvx", "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")))
HR_LINE = "─" * 8


def to_script(body, table):
    """按映射表转上下标，遇到未收录字符返回空。"""
    out = []
    for ch in body:
        if ch.lower() not in table:
            return ""
        out.append(table[ch.lower()])
    return "".join(out)


def task_mark(text):
    """任务列表标记转为勾选框。"""
    return re.sub(r"^\[([ xX])\]\s*", lambda m: "☑ " if m.group(1).lower() == "x" else "☐ ", text)


def markdown_text(text):
    """Markdown 结构转普通文本：任务列表、引用、分隔线、链接、标签、脚注、上下标。"""
    m = MD_TASK.match(text)
    if m:
        return "%s%s %s" % (m.group(1), "☑" if m.group(2).lower() == "x" else "☐",
                            markdown_text(m.group(3)))
    text = task_mark(text)
    m = MD_QUOTE.match(text)
    if m:
        return "%s▏%s" % ("  " * (len(m.group(2)) - 1), markdown_text(m.group(3)))
    if MD_HR.match(text):
        return HR_LINE
    m = MD_DEF.match(text)
    if m:
        return "    · " + markdown_text(m.group(1))
    m = MD_FOOT.match(text)
    if m:
        return "脚注[^%s]：%s" % (m.group(1), m.group(2))
    text = MD_LINK.sub(lambda m: ("图片：%s（%s）" % (m.group(2) or "无说明", m.group(3)))
                       if m.group(1) else ("%s（%s）" % (m.group(2), m.group(3))), text)
    text = MD_AUTO.sub(lambda m: m.group(1) or m.group(2), text)
    text = MD_BR.sub("\n", text)
    text = MD_TAG.sub("", text)
    text = MD_SUB_MARK.sub(lambda m: to_script(m.group(1), SUB_MAP) or m.group(0), text)
    return MD_SUP_MARK.sub(lambda m: to_script(m.group(1), SUPER_MAP) or m.group(0), text)


# ---------------- 菜单与输入 ----------------

def ask_choice(prompt):
    print(prompt)
    try:
        return input("> ").strip()
    except EOFError:
        return ""


def ask_format():
    """询问输入格式，非法输入回退自动识别。"""
    global FMT
    fmt = ask_choice(t("fmt_menu"))
    if fmt in ("1", "2", "3", "4", "5", "6", "7"):
        FMT = int(fmt)
        print(t("fmt_%d" % FMT))
    elif fmt:
        print("※ " + t("bad_fmt"))


def read_content():
    print(t("paste_hint"))
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        # 行内含结束标记时只保留标记前的内容
        if END_MARK in line:
            head = line[:line.index(END_MARK)].rstrip()
            if head:
                lines.append(head)
            break
        lines.append(line)
    return "\n".join(lines)


# ---------------- LaTeX 转普通文本 ----------------

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "θ", "iota": "ι", "kappa": "κ",
    "varkappa": "ϰ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "omicron": "ο",
    "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς",
    "tau": "τ", "upsilon": "υ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "digamma": "ϝ",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

SYMBOLS = {
    # 运算
    "times": "×", "div": "÷", "pm": "±", "mp": "∓", "cdot": "·", "ast": "∗",
    "star": "⋆", "circ": "∘", "bullet": "•", "oplus": "⊕", "ominus": "⊖",
    "otimes": "⊗", "oslash": "⊘", "odot": "⊙", "dagger": "†", "ddagger": "‡",
    # 关系
    "le": "≤", "leq": "≤", "leqslant": "≤", "ge": "≥", "geq": "≥", "geqslant": "≥",
    "ne": "≠", "neq": "≠", "equiv": "≡", "approx": "≈", "cong": "≅", "simeq": "≃",
    "sim": "∼", "propto": "∝", "prec": "≺", "succ": "≻", "ll": "≪", "gg": "≫",
    "subset": "⊂", "subseteq": "⊆", "subsetneq": "⊊", "supset": "⊃", "supseteq": "⊇",
    "supsetneq": "⊋", "sqsubseteq": "⊑", "sqsupseteq": "⊒", "doteq": "≐", "asymp": "≍",
    "bowtie": "⋈", "models": "⊨", "vdash": "⊢", "dashv": "⊣", "perp": "⊥",
    "parallel": "∥", "nparallel": "∦", "mid": "|", "nmid": "∤", "vert": "|", "Vert": "‖",
    # 集合与逻辑
    "in": "∈", "ni": "∋", "notin": "∉", "cup": "∪", "cap": "∩", "sqcup": "⊔",
    "sqcap": "⊓", "emptyset": "∅", "varnothing": "∅", "setminus": "∖", "complement": "∁",
    "forall": "∀", "exists": "∃", "nexists": "∄", "neg": "¬", "lnot": "¬",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨", "therefore": "∴", "because": "∵",
    "top": "⊤", "bot": "⊥",
    # 箭头
    "to": "→", "gets": "←", "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "iff": "⇔", "implies": "⇒",
    "longrightarrow": "⟶", "longleftarrow": "⟵", "longleftrightarrow": "⟷",
    "Longrightarrow": "⟹", "Longleftarrow": "⟸", "Longleftrightarrow": "⟺",
    "mapsto": "↦", "longmapsto": "⟼", "uparrow": "↑", "downarrow": "↓", "updownarrow": "↕",
    "Uparrow": "⇑", "Downarrow": "⇓", "Updownarrow": "⇕", "hookrightarrow": "↪",
    "hookleftarrow": "↩", "nearrow": "↗", "searrow": "↘", "swarrow": "↙", "nwarrow": "↖",
    "rightharpoonup": "⇀", "leftharpoonup": "↼", "rightleftharpoons": "⇌",
    # 其它常用符号
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏", "coprod": "∐",
    "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮", "angle": "∠",
    "measuredangle": "∡", "triangle": "△", "square": "□", "Box": "□", "Diamond": "◇",
    "diamond": "⋄", "bigcirc": "○", "ldots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "dots": "…", "hbar": "ℏ", "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ", "wp": "℘",
    "prime": "′", "degree": "°", "S": "§", "P": "¶", "copyright": "©", "pounds": "£",
    "checkmark": "✓", "flat": "♭", "sharp": "♯", "clubsuit": "♣", "diamondsuit": "♢",
    "heartsuit": "♡", "spadesuit": "♤", "cbrt": "∛", "surd": "√",
}

TEXT_CMDS = ("text", "textrm", "textbf", "textit", "texttt", "textsf", "textnormal",
             "mbox", "mathrm", "operatorname", "textsuperscript", "textsubscript")
# 去壳保留内容的字体/包裹命令
SHELL_CMDS = ("mathbf", "boldsymbol", "bm", "mathbb", "mathcal", "mathfrak", "mathsf",
              "mathtt", "mathit", "mathop", "mathrel", "boxed", "cancel", "phantom",
              "hspace", "overbrace", "underbrace", "overline", "underline", "ce")
# 去壳并加组合字符的重音命令
ACCENTS = {"hat": "\u0302", "widehat": "\u0302", "bar": "\u0304", "tilde": "\u0303",
           "widetilde": "\u0303", "dot": "\u0307", "ddot": "\u0308", "acute": "\u0301",
           "grave": "\u0300", "breve": "\u0306", "check": "\u030c", "mathring": "\u030a",
           "vec": "\u20d7", "overrightarrow": "\u20d7", "overleftarrow": "\u20d6"}
# 直接照写的函数名
FUNCS = ("sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan",
         "sinh", "cosh", "tanh", "coth", "exp", "log", "ln", "lg", "lim", "limsup",
         "liminf", "sup", "inf", "max", "min", "det", "dim", "ker", "hom", "arg",
         "deg", "gcd", "lcm", "Pr", "mod", "bmod", "pmod")
# 无输出或仅排版的命令
DROP_CMDS = ("limits", "nolimits", "displaystyle", "textstyle", "scriptstyle",
             "scriptscriptstyle", "hline", "big", "Big", "bigg", "Bigg", "bigl",
             "bigr", "Bigl", "Bigr", "biggl", "biggr", "Biggl", "Biggr", "mathstrut",
             "allowbreak", "nonumber", "notag", "qedhere")
# \not + 关系符的合并结果
NEGATED = {"in": "∉", "ni": "∌", "subset": "⊄", "supset": "⊅", "subseteq": "⊈",
           "supseteq": "⊉", "le": "≰", "leq": "≰", "ge": "≱", "geq": "≱",
           "equiv": "≢", "approx": "≉", "sim": "≁", "mid": "∤", "parallel": "∦",
           "exists": "∄", "=": "≠", "owns": "∌"}
# 宏包单位命令
UNITS = {"per": "/", "hour": "h", "kilo": "k", "meter": "m", "metre": "m",
         "second": "s", "gram": "g", "litre": "L", "liter": "L", "celsius": "°C",
         "kelvin": "K", "mole": "mol", "ampere": "A", "volt": "V", "watt": "W"} 
# 取上下标的中缀写法：{a \choose b}
INFIX_RE = re.compile(r"\{([^{}]*)\\(choose|atop|over)\s*([^{}]*)\}")


def split_group(s, start):
    """从 s[start] 的左花括号读到匹配的右花括号，返回(组内内容, 结束位置)。"""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    return s[start + 1:], len(s)


VSPACE = {"quad": "  ", "qquad": "    "}
OP_CMDS = {"lim": "lim", "limsup": "lim sup", "liminf": "lim inf",
           "sum": "∑", "prod": "∏", "int": "∫", "iint": "∬", "oint": "∮",
           "max": "max", "min": "min", "sup": "sup", "inf": "inf", "log": "log", "ln": "ln"}


def infix_frac(m):
    """把 {a \\choose b} 之类的中缀写法转成函数形式。"""
    left, right = m.group(1).strip(), m.group(3).strip()
    if m.group(2) == "choose":
        return "C(%s,%s)" % (left, right)
    return "(%s)/(%s)" % (left, right)


def read_script(s, start):
    """读取一个上下标参数的原文，返回(原文, 结束位置)；没有则返回 None。"""
    if start >= len(s) or s[start] not in "^_":
        return None
    pos = start + 1
    if pos >= len(s):
        return "", pos
    if s[pos] == "{":
        return split_group(s, pos)
    m = re.match(r"\\([A-Za-z]+)", s[pos:])
    if m:
        return m.group(0), pos + m.end()
    return s[pos], pos + 1


def read_env_body(s, start, env):
    """读取 \\begin 环境的内容，返回(内容, 结束位置)。"""
    mark = "\\end{%s}" % env
    pos = s.find(mark, start)
    if pos == -1:
        return s[start:], len(s)
    return s[start:pos], pos + len(mark)


# 环境排版：括号样式，未列出的环境不加壳
ENVS = {
    "matrix": ("", ""), "smallmatrix": ("", ""),
    "pmatrix": ("( ", " )"), "bmatrix": ("[ ", " ]"),
    "Bmatrix": ("{ ", " }"), "vmatrix": ("| ", " |"), "Vmatrix": ("‖ ", " ‖"),
    "cases": ("{ ", " }"), "rcases": ("", " }"), "dcases": ("{ ", " }"),
    "aligned": ("", ""), "align": ("", ""), "alignedat": ("", ""),
    "gather": ("", ""), "multline": ("", ""), "split": ("", ""),
    "eqnarray": ("", ""), "array": ("", ""), "subarray": ("", ""),
    "equation": ("", ""), "displaymath": ("", ""),
}
ENV_DEFAULT = ("", "")


ARG_ENVS = ("array", "tabular", "alignedat", "subarray")


def skip_env_args(s, start):
    """跳过环境的列格式参数，最多两对方括号或花括号组。"""
    i = start
    for _ in range(2):
        while i < len(s) and s[i] in " \t":
            i += 1
        if i < len(s) and s[i] == "{":
            _body, i = split_group(s, i)
        elif i < len(s) and s[i] == "[":
            end = s.find("]", i)
            if end == -1:
                break
            i = end + 1
        else:
            break
    return i


def render_env(env, body, prefix=""):
    """把矩阵、分段函数等环境排成多行文本，续行按行内前缀缩进。"""
    grid = []
    for row in body.split("\\\\"):
        cells = [latex_to_plain(c).replace("\n", " ").strip() for c in row.split("&")]
        if any(cells):
            grid.append(cells)
    if not grid:
        return ""
    cols = max(len(r) for r in grid)
    for r in grid:
        while len(r) < cols:
            r.append("")
    widths = [max(w(r[k]) for r in grid) for k in range(cols)]
    lines = ["  ".join(c + " " * (widths[k] - w(c)) for k, c in enumerate(r)).rstrip()
             for r in grid]
    head, tail = ENVS.get(env.rstrip("*"), ENV_DEFAULT)
    if len(lines) == 1:
        return head + lines[0] + tail
    pad = " " * (w(prefix) + w(head))
    out = [head + lines[0]]
    out.extend(pad + x for x in lines[1:])
    out[-1] += tail
    return "\n".join(out)


def latex_to_plain(s, prefix=""):
    """把一段 LaTeX 写法转成普通文本，prefix 为同行已有内容，用于多行环境对齐。"""
    s = INFIX_RE.sub(infix_frac, s)
    s = re.sub(r"\\left(?![A-Za-z])", "", s)
    s = re.sub(r"\\right(?![A-Za-z])", "", s)
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i:i + 2] == "\\\\":
            out.append("\n")
            i += 2
            continue
        ch = s[i]
        if ch == "\\":
            if i + 1 < n and s[i + 1] in ",;: ":
                out.append(" ")
                i += 2
                continue
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if not m:
                i += 2
                continue
            name = m.group(1)
            j = i + len(name) + 1
            if name in ("frac", "dfrac", "tfrac", "cfrac"):
                num, j = read_next_group(s, j)
                den, j = read_next_group(s, j)
                out.append("(%s)/(%s)" % (latex_to_plain(num), latex_to_plain(den)))
            elif name == "genfrac":
                left, j = read_next_group(s, j)
                right, j = read_next_group(s, j)
                _thick, j = read_next_group(s, j)
                _style, j = read_next_group(s, j)
                num, j = read_next_group(s, j)
                den, j = read_next_group(s, j)
                out.append("%s%s/%s%s" % (latex_to_plain(left).strip(), latex_to_plain(num),
                                          latex_to_plain(den), latex_to_plain(right).strip()))
            elif name == "sqrt":
                idx = ""
                if j < n and s[j] == "[":
                    idx, j = read_next_group(s, j)
                body, j = read_next_group(s, j)
                body = latex_to_plain(body)
                if idx == "3":
                    out.append("∛(%s)" % body)
                elif idx == "4":
                    out.append("∜(%s)" % body)
                elif idx:
                    out.append("%s次根号(%s)" % (idx, body))
                else:
                    out.append("√(%s)" % body)
            elif name == "begin":
                env, j = read_next_group(s, j)
                if env.rstrip("*") in ARG_ENVS:
                    j = skip_env_args(s, j)
                body, j = read_env_body(s, j, env)
                # 续行缩进取本行已有内容；公式内换行后前缀作废
                line = (prefix + "".join(out)).rsplit("\n", 1)[-1]
                out.append(render_env(env, body, line))
            elif name == "end":
                env, j = read_next_group(s, j)
            elif name in TEXT_CMDS:
                body, j = read_next_group(s, j)
                out.append(body)
            elif name in SHELL_CMDS:
                body, j = read_next_group(s, j)
                out.append(latex_to_plain(body))
            elif name in ACCENTS:
                body, j = read_next_group(s, j)
                out.append(latex_to_plain(body) + ACCENTS[name])
            elif name in ("stackrel", "overset", "underset"):
                top, j = read_next_group(s, j)
                base, j = read_next_group(s, j)
                out.append("%s(%s)" % (latex_to_plain(base), latex_to_plain(top)))
            elif name == "substack":
                body, j = read_next_group(s, j)
                rows = [latex_to_plain(x).strip() for x in body.split("\\\\")]
                out.append(", ".join(x for x in rows if x))
            elif name == "not":
                m2 = re.match(r"\\([A-Za-z]+)", s[j:])
                if m2 and m2.group(1) in NEGATED:
                    out.append(NEGATED[m2.group(1)])
                    j += m2.end()
                elif s[j:j + 1] == "=":
                    out.append("≠")
                    j += 1
                else:
                    out.append("¬")
            elif name == "pmod":
                body, j = read_next_group(s, j)
                out.append("(mod %s)" % latex_to_plain(body).strip())
            elif name in ("bra", "ket", "braket", "expval"):
                body, j = read_next_group(s, j)
                text = latex_to_plain(body).strip()
                k = j
                while k < len(s) and s[k] == " ":
                    k += 1
                if k < len(s) and s[k] == "{":
                    other, j = split_group(s, k)
                    text += "|" + latex_to_plain(other).strip()
                if name == "ket":
                    out.append("|" + text + "⟩")
                elif name == "bra":
                    out.append("⟨" + text + "|")
                else:
                    out.append("⟨" + text + "⟩")
            elif name in ("dv", "pdv"):
                a, j = read_next_group(s, j)
                d = "∂" if name == "pdv" else "d"
                k = j
                while k < len(s) and s[k] == " ":
                    k += 1
                if k < len(s) and s[k] == "{":
                    b, j = split_group(s, k)
                    out.append("%s%s/%s%s" % (d, latex_to_plain(a).strip(), d,
                                              latex_to_plain(b).strip()))
                else:
                    out.append("%s/%s%s" % (d, d, latex_to_plain(a).strip()))
            elif name in ("SI", "qty", "num", "ang", "pu"):
                args = []
                while j < len(s):
                    while j < len(s) and s[j] == " ":
                        j += 1
                    if j >= len(s) or s[j] not in "{[":
                        break
                    arg, j = read_next_group(s, j)
                    args.append(latex_to_plain(arg).strip())
                text = " ".join(x for x in args if x).replace("//", "/")
                out.append(text + ("°" if name == "ang" else ""))
            elif name in UNITS:
                out.append(UNITS[name])
            elif name in DROP_CMDS:
                pass
            elif name in ("binom", "dbinom", "tbinom"):
                top, j = read_next_group(s, j)
                bottom, j = read_next_group(s, j)
                out.append("C(%s,%s)" % (latex_to_plain(top).strip(), latex_to_plain(bottom).strip()))
            elif name in VSPACE:
                out.append(VSPACE[name])
            elif name in OP_CMDS:
                out.append(OP_CMDS[name])
                bounds = []
                while len(bounds) < 2:
                    got = read_script(s, j)
                    if not got:
                        break
                    bounds.append(latex_to_plain(got[0]).strip())
                    j = got[1]
                if bounds:
                    out.append("(%s)" % "..".join(bounds))
            elif name in FUNCS:
                out.append(name)
            elif name in GREEK:
                out.append(GREEK[name])
            elif name in SYMBOLS:
                out.append(SYMBOLS[name])
            else:
                out.append(name)
            i = j
            continue
        if ch in "^_":
            got = read_script(s, i)
            if got and got[0]:
                out.append(ch + latex_to_plain(got[0]))
                i = got[1]
                continue
            i += 1
            continue
        if ch in "{}":
            i += 1
            continue
        if ch == "&":
            out.append("  ")
            i += 1
            continue
        if ch == "~":
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def read_next_group(s, start):
    """读取下一个参数（方括号、花括号组或单字符），返回(内容, 结束位置)。"""
    if start < len(s) and s[start] == "[":
        end = s.find("]", start)
        if end != -1:
            return s[start + 1:end], end + 1
    if start < len(s) and s[start] == "{":
        return split_group(s, start)
    if start < len(s):
        return s[start], start + 1
    return "", start


EMPH_RE = re.compile(r"(\*\*\*|\*\*|__|~~|==|`|\*|_)([^\s{}]*?)\1")


def is_edge(ch):
    """侧翼判定：行首/行尾、空白、标点或环境占位符算边界。"""
    return ch is None or ch.isspace() or unicodedata.category(ch).startswith("P") \
        or ch in (ENV_MARK, ENV_MARK_END)


def strip_emphasis(text):
    """按侧翼规则删除成对强调标记，其余原样保留。"""
    def repl(m):
        before = text[m.start() - 1] if m.start() else None
        after = text[m.end()] if m.end() < len(text) else None
        if m.group(2) and is_edge(before) and is_edge(after):
            return m.group(2)
        return m.group(0)
    return EMPH_RE.sub(repl, text)


STRUCT_CMDS = ("frac|dfrac|tfrac|cfrac|sqrt|binom|dbinom|tbinom|genfrac|stackrel"
               "|overset|underset|substack|not|pmod|bra|ket|braket|expval|dv|pdv"
               "|SI|qty|num|ang|pu")
KNOWN_CMDS = (STRUCT_CMDS + "|"
              + "|".join(TEXT_CMDS + SHELL_CMDS + FUNCS + DROP_CMDS + tuple(ACCENTS) + tuple(UNITS))
              + "|" + "|".join(GREEK) + "|" + "|".join(SYMBOLS))
ARG_CMDS = re.compile(r"\\(?:%s)(?![A-Za-z])\s*(?:\{[^{}]*\}){1,2}" % KNOWN_CMDS)
PLAIN_CMDS = re.compile(r"\\(?:%s)(?![A-Za-z])" % KNOWN_CMDS)
# 命令名后紧跟的上下标参数一并吃掉，避免裸公式漏转
SCRIPT_ARG = r"(?:\{[^{}]*\}|\\[A-Za-z]+|[A-Za-z0-9])"
SCRIPT_CMDS = re.compile(r"\\(?:%s)(?![A-Za-z])[_^]%s(?:[_^]%s)*"
                         % (KNOWN_CMDS, SCRIPT_ARG, SCRIPT_ARG))
# \limits / \nolimits 只影响排版，无输出
LIMITS_RE = re.compile(r"\\(?:limits|nolimits)(?![A-Za-z])")


def convert_bare_latex(text):
    """把正文中无定界符的常见 LaTeX 写法也转成普通文本。"""
    text = LIMITS_RE.sub("", text)
    for _ in range(2):
        new = SCRIPT_CMDS.sub(lambda m: latex_to_plain(m.group(0)), text)
        new = ARG_CMDS.sub(lambda m: latex_to_plain(m.group(0)), new)
        new = PLAIN_CMDS.sub(lambda m: latex_to_plain(m.group(0)), new)
        if new == text:
            break
        text = new
    return text


def split_math(text, warnings):
    """按 $$、$、\\( 定界符切分，返回 (kind, 内容) 列表。"""
    segments = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("$$", i):
            end = text.find("$$", i + 2)
            if end == -1:
                segments.append(("txt", text[i:]))
                warnings.add("unclosed_formula")
                i = n
                continue
            segments.append(("math", text[i + 2:end]))
            i = end + 2
            continue
        if text.startswith("\\(", i):
            end = text.find("\\)", i + 2)
            if end == -1:
                segments.append(("txt", text[i:]))
                warnings.add("unclosed_formula")
                i = n
                continue
            segments.append(("math", text[i + 2:end]))
            i = end + 2
            continue
        if text[i] == "$":
            end = text.find("$", i + 1)
            if end == -1:
                segments.append(("txt", text[i:]))
                warnings.add("unclosed_formula")
                i = n
                continue
            segments.append(("math", text[i + 1:end]))
            i = end + 1
            continue
        j = text.find("$", i)
        k = text.find("\\(", i)
        cands = [x for x in (j, k) if x != -1]
        nxt = min(cands) if cands else n
        if nxt > i:
            segments.append(("txt", text[i:nxt]))
        i = nxt if cands else n
    return segments


def convert_inline(text, warnings, bare_math=False, markdown=False):
    """行内处理：公式转普通文本 + 删除强调，markdown 时先转 Markdown 结构。"""
    parts = []
    for kind, seg in split_math(text, warnings):
        if kind == "math":
            parts.append(latex_to_plain(seg.strip(), "".join(parts).rsplit("\n", 1)[-1]))
            continue
        plain = markdown_text(seg) if markdown else seg
        plain = strip_emphasis(plain)
        if bare_math:
            plain = convert_bare_latex(plain)
        parts.append(plain)
    return "".join(parts)


def join_block_math(text):
    """把跨行的 $$ 公式合并成一行。"""
    out = []
    buf = None
    for line in text.split("\n"):
        s = line.strip()
        if buf is None:
            if s.startswith("$$") and s.count("$$") == 1:
                buf = [s]
                continue
            out.append(line)
            continue
        buf.append(s)
        if s.endswith("$$"):
            out.append(" ".join(buf))
            buf = None
    if buf is not None:
        out.extend(buf)
    return "\n".join(out)


# ---------------- 文档切块 ----------------

def split_blocks(text):
    """按 ``` 围栏切块，返回 (kind, 内容, 语言标记) 列表，kind 为 code/para。"""
    blocks = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            label = lines[i].strip().strip("`").strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            if j >= len(lines):
                blocks.append(("code", "\n".join(lines[i + 1:]), label))
                i = len(lines)
            else:
                blocks.append(("code", "\n".join(lines[i + 1:j]), label))
                i = j + 1
        else:
            j = i
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            blocks.append(("para", "\n".join(lines[i:j]), ""))
            i = j
    return blocks


LIST_RE = re.compile(r"^(\s*)([-*+]\s+|\d+[.)]\s+)(.*)$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
PIPE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


# ---------------- 分块与结构转换 ----------------

def clean_node(text, warnings, markdown=True):
    """把节点文本里的公式、Markdown 结构与强调清理掉。"""
    return convert_inline(text.strip(), warnings, markdown=markdown)


def is_table_row(line):
    s = line.strip()
    return s.startswith("|") or s.count("|") >= 1


def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def render_table(rows, warnings):
    cells = [split_row(r) for r in rows if not PIPE_SEP_RE.match(r)]
    cells = [r for r in cells if any(c for c in r)]
    return render_cells(cells, warnings)


def render_cells(cells, warnings):
    """按单元格渲染对齐字符表格。"""
    if not cells:
        return ""
    cols = max(len(r) for r in cells)
    for r in cells:
        while len(r) < cols:
            r.append("")
    plain = [[clean_node(c, warnings).replace("\n", " ") for c in r] for r in cells]
    widths = [max(w(r[i]) for r in plain) for i in range(cols)]
    sep = "|" + "|".join("-" * (width + 2) for width in widths) + "|"
    out = []
    for idx, r in enumerate(plain):
        line = "|" + "|".join(
            " " + c + " " * (widths[i] - w(c) + 1) for i, c in enumerate(r)
        ) + "|"
        out.append(line)
        if idx == 0:
            out.append(sep)
    return "\n".join(out)


MATHY_RE = re.compile(r"[$\\^]|^\s*#")
NUM_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
BOX_RE = re.compile(r"[\u2500-\u257f]")


def looks_like_edge(line):
    """判断一行是否像流程图连线写法。"""
    s = line.strip()
    if "-->" in s or "->" in s or "==>" in s:
        return True
    return bool(re.match(r"^(graph|flowchart|mindmap)\b", s, re.I))


EDGE_SPLIT = re.compile(r"-->|==>|-\.->|---|->|--")
NODE_TOKEN_RE = re.compile(r"^[\w\u4e00-\u9fff]+(?:\s*[\[\{\(][^\]\}\)]*[\]\)\}]+)?$")


def is_flow_line(s):
    """判断一行是否由箭头连接的节点构成，排除代码与句子。"""
    s = s.strip().rstrip(";").strip()
    if not looks_like_edge(s):
        return False
    s = re.sub(r"(-->|==>|-\.->)\s*\|[^|]*\|", r"\1", s)
    s = re.sub(r"-\.\s*[^.]*?\s*\.->", "-.->", s)
    s = re.sub(r"--\s+[^-|]+?\s+-->", "-->", s)
    parts = [p.strip() for p in EDGE_SPLIT.split(s) if p.strip()]
    return len(parts) >= 2 and all(NODE_TOKEN_RE.match(p) for p in parts)


def flow_run_start(s):
    """判断一行是否是裸流程图段落的开头。"""
    if re.match(r"^(graph|flowchart)\b", s, re.I):
        return True
    return is_flow_line(s)


def collect_flow_run(lines, i):
    """收集连续的裸流程图行，返回 (行列表, 结束下标)。"""
    node_def = re.compile(r"^[A-Za-z0-9一-鿿]+\s*[\[\{\(]")
    n = len(lines)
    j = i
    run = []
    while j < n and lines[j].strip() \
            and not lines[j].strip().lower().startswith("mindmap") \
            and (looks_like_edge(lines[j]) or node_def.match(lines[j].strip())):
        run.append(lines[j])
        j += 1
    return run, j


def match_pipe_table(lines, i):
    """识别管道表格，返回 (行列表, 结束下标) 或 None。"""
    head = lines[i].strip()
    if head.count("|") < 2 and not head.startswith("|"):
        return None
    if looks_like_edge(head):
        return None
    n = len(lines)
    rows = [lines[i]]
    j = i + 1
    has_sep = j < n and bool(PIPE_SEP_RE.match(lines[j]))
    if has_sep:
        rows.append(lines[j])
        j += 1
    while j < n and lines[j].strip() and is_table_row(lines[j]) \
            and not PIPE_SEP_RE.match(lines[j]) and not looks_like_edge(lines[j]):
        rows.append(lines[j])
        j += 1
    if not has_sep:
        # 没有分隔行时，要求连续多行且竖线数量一致
        body = [r for r in rows if not PIPE_SEP_RE.match(r)]
        if len(body) < 2 or len({r.count("|") for r in body}) != 1:
            return None
        if body[0].count("|") < 3:
            return None
    return rows, j


def match_ws_table(lines, i):
    """识别无竖线的空白分隔表格，返回 (行列表, 结束下标) 或 None。"""
    n = len(lines)
    head = lines[i].strip()
    cols = len(head.split())
    if cols < 3 or i + 2 >= n:
        return None
    if re.search(r"[。！？!?]", head) or MATHY_RE.search(head) or looks_like_edge(head):
        return None
    rows = [head]
    j = i + 1
    same = 0
    total = 0
    while j < n:
        s = lines[j].strip()
        if not s or "|" in s or LIST_RE.match(lines[j]) or HEAD_RE.match(lines[j]):
            break
        if re.search(r"[。！？!?]", s) or MATHY_RE.search(s) or looks_like_edge(s):
            break
        c = len(s.split())
        if c < cols - 1 or c > cols + 1:
            break
        total += 1
        if c == cols:
            same += 1
        rows.append(s)
        j += 1
    if total < 2 or same < (total + 1) // 2:
        return None
    if any(BOX_RE.search(r) for r in rows):
        return None
    # 无对齐排版又无数字列的块按普通段落处理，避免把列表当表格
    aligned = any(re.search(r"\S {2,}\S", r) for r in rows)
    numeric = sum(1 for r in rows if any(NUM_RE.match(c) for c in r.split()))
    if not aligned and numeric * 2 < len(rows):
        return None
    return rows, j


def split_ws_cells(line, cols):
    """按空白切分，多出的字段并入末列。"""
    tokens = line.split()
    if len(tokens) > cols:
        tokens = tokens[:cols - 1] + [" ".join(tokens[cols - 1:])]
    return tokens


def render_ws_table(rows, warnings):
    """渲染无竖线表格。"""
    cols = len(rows[0].split())
    return render_cells([split_ws_cells(r, cols) for r in rows], warnings)


def match_bare_mindmap(lines, i):
    """识别没有代码围栏的 mindmap 段落，返回 (块行列表, 结束下标) 或 None。"""
    if lines[i].strip().lower() != "mindmap":
        return None
    base = len(lines[i]) - len(lines[i].lstrip())
    block = [lines[i]]
    j = i + 1
    while j < len(lines) and len(block) <= 200:
        raw = lines[j]
        if not raw.strip() or len(raw) - len(raw.lstrip()) <= base:
            break
        block.append(raw)
        j += 1
    if len(block) < 2 or not looks_like_mindmap(block):
        return None
    return block, j


def list_depth(line):
    m = LIST_RE.match(line)
    if not m:
        return None, None
    indent = len(m.group(1).replace("\t", "  "))
    return indent, m.group(3)


def tree_lines(items, root_bracket=True):
    """把 (层级, 文本) 列表渲染成带连接线的树；root_bracket 为假时顶层也画分支。"""
    n = len(items)
    last = [True] * n
    for i in range(n):
        lvl = items[i][0]
        for j in range(i + 1, n):
            if items[j][0] < lvl:
                break
            if items[j][0] == lvl:
                last[i] = False
                break
    out = []
    for i, (lvl, text) in enumerate(items):
        if root_bracket and lvl <= 1:
            out.append("【" + text + "】")
            continue
        prefix = ""
        for d in range(1 if not root_bracket else 2, lvl):
            anc = None
            for j in range(i - 1, -1, -1):
                if items[j][0] < d:
                    break
                if items[j][0] == d:
                    anc = j
                    break
            prefix += "   " if anc is None or last[anc] else "│  "
        prefix += "└── " if last[i] else "├── "
        out.append(prefix + text)
    return out


def mermaid_to_tree(lines, warnings):
    """mindmap 转带连接线的树。"""
    raw_items = []
    for raw in lines:
        if not raw.strip() or raw.strip().lower().startswith("mindmap"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        shape = raw.strip()
        shape = re.sub(r"^[\w\u4e00-\u9fff]+\s*[\[\(\{]+(.*?)[\]\)\}]+\s*$", r"\1", shape)
        shape = re.sub(r"[\[\]{}()]", "", shape).strip()
        raw_items.append((indent, shape))
    if not raw_items:
        return ""
    ranks = {ind: k + 1 for k, ind in enumerate(sorted({ind for ind, _ in raw_items}))}
    items = []
    for indent, shape in raw_items:
        text = clean_node(shape, warnings, markdown=False) or shape
        items.append((ranks[indent], text))
    return "\n".join(tree_lines(items))


FLOW_HEAD = ("graph", "flowchart", "mindmap", "subgraph", "end", "style", "classdef",
             "class", "linkstyle", "click", "direction", "%%")
FLOW_ARROW = r"-->|==>|-\.->|---|--"


def flow_node(token, nodes, order):
    """登记流程图节点，返回(编号, 名称)。"""
    t = token.strip()
    m = re.match(r"^([\w\u4e00-\u9fff]+)\s*[\[\(\{]+(.*?)[\]\)\}]+\s*$", t)
    if m:
        key, name = m.group(1), m.group(2)
    else:
        key = name = t
    name = re.sub(r"[\[\]{}()]", " ", name)
    name = re.sub(r"\s+", " ", name).strip() or key
    if key not in nodes:
        idx = len(order)
        nodes[key] = chr(ord("A") + idx) if idx < 26 else str(idx + 1)
        order.append((key, name))
    return nodes[key], name


def mermaid_to_flow(lines, warnings):
    """graph/flowchart 转节点清单与连线，subgraph 保留层级。"""
    nodes = {}
    order = []
    edges = []
    groups = []
    for raw in lines:
        s = raw.strip()
        low = s.lower()
        if not s:
            continue
        if low.startswith("subgraph"):
            title = clean_node(s[len("subgraph"):].strip(), warnings, markdown=False) or "分组"
            groups.append(title)
            continue
        if low == "end":
            if groups:
                groups.pop()
            continue
        if low.startswith(FLOW_HEAD):
            continue
        if s.endswith(";"):
            s = s[:-1]
        labels = []

        def take_label(m):
            labels.append(m.group(2).strip())
            return m.group(1)

        s = re.sub(r"(-->|==>|-\.->)\s*\|([^|]*)\|", take_label, s)
        s = re.sub(r"-\.\s*([^.]*?)\s*\.->", lambda m: (labels.append(m.group(1).strip()), "-.->")[1], s)
        s = re.sub(r"--\s*([^->|]+?)\s*-->", lambda m: (labels.append(m.group(1).strip()), "-->")[1], s)
        tokens = [t for t in re.split(FLOW_ARROW, s) if t.strip()]
        ids = [flow_node(t, nodes, order)[0] for t in tokens]
        prefix = "  " * len(groups) if groups else ""
        if groups and len(ids) == 1:
            edges.append((prefix + "组：%s" % groups[-1], "", ""))
            continue
        for k in range(len(ids) - 1):
            edges.append((prefix + ids[k], ids[k + 1], labels[k] if k < len(labels) else ""))
    head = ["%s：%s" % (nodes[key], clean_node(name, warnings, markdown=False)) for key, name in order]
    body = []
    for a, b, lab in edges:
        if not b:
            body.append(a)
            continue
        body.append("%s → %s%s" % (a, b, ("（%s）" % lab) if lab else ""))
    return "\n".join(head + ([""] + body if body else []))


# mermaid 图类型：小写前缀 → 中文名
DIAGRAMS = {
    "sequencediagram": "时序图",
    "classdiagram": "类图",
    "statediagram": "状态图",
    "erdiagram": "实体关系图",
    "journey": "用户旅程图",
    "pie": "饼图",
    "gantt": "甘特图",
    "gitgraph": "提交图",
    "quadrantchart": "象限图",
    "requirementdiagram": "需求图",
    "timeline": "时间线",
    "sankey-beta": "桑基图",
    "xychart-beta": "坐标图",
    "block-beta": "块图",
    "c4context": "C4 上下文图",
}
SEQ_ARROW = {"->>": "→", "->": "→", "-->>": "⇢", "-->": "⇢", "-x": "×", "--x": "×",
             "-)": ")", "--)": ")"}
SEQ_LABEL = {"alt": "分支", "else": "否则", "opt": "可选", "loop": "循环", "par": "并行",
             "critical": "关键", "break": "中断", "rect": "区域"}
REL_KINDS = (("<|--", "继承"), ("--|>", "继承"), ("<|..", "实现"), ("..|>", "实现"),
             ("*--", "组合"), ("--*", "组合"), ("o--", "聚合"), ("--o", "聚合"),
             ("..>", "依赖"), ("<..", "依赖"), ("-->", "指向"), ("<--", "指向"),
             ("--", "关联"), ("..", "关联"))
ER_CARD = {"||": "1", "|o": "0..1", "o|": "0..1", "}o": "多", "o{": "多",
           "}|": "1..多", "|{": "1..多", "}{": "多"}


def diagram_kind(low):
    """返回 mermaid 图类型键，未识别返回空串。"""
    for key in DIAGRAMS:
        if low.startswith(key):
            return key
    return ""


def actor_name(name, actors):
    """参与者标识替换为显示名。"""
    return actors.get(name, name)


def sequence_text(lines):
    """时序图转参与者与消息顺序。"""
    actors = {}
    steps = []
    for raw in lines:
        s = raw.strip()
        low = s.lower()
        if not s or low.startswith("sequencediagram") or low == "end":
            continue
        m = re.match(r"(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?$", s, re.I)
        if m:
            actors[m.group(1)] = (m.group(2) or m.group(1)).strip()
            continue
        m = re.match(r"note\s+(?:over|left of|right of)\s+[^:]+:\s*(.*)$", s, re.I)
        if m:
            steps.append("注：%s" % m.group(1).strip())
            continue
        m = re.match(r"(\w+)\b\s*(.*)$", s)
        if m and m.group(1).lower() in SEQ_LABEL:
            steps.append("%s：%s" % (SEQ_LABEL[m.group(1).lower()], m.group(2).strip()))
            continue
        if low.startswith(("activate", "deactivate")):
            continue
        m = re.match(r"^(.+?)\s*(-{1,2}(?:>>|>|x|\)))\s*(.+?)\s*:\s*(.*)$", s)
        if m:
            steps.append("%s %s %s：%s" % (actor_name(m.group(1).strip(), actors),
                                           SEQ_ARROW.get(m.group(2), "→"),
                                           actor_name(m.group(3).strip(), actors),
                                           m.group(4).strip()))
            continue
        steps.append(s)
    out = []
    if actors:
        out.append("参与者：" + " / ".join("%s %s" % (k, v) for k, v in actors.items()))
    out.extend("%d. %s" % (i + 1, x) for i, x in enumerate(steps))
    return "\n".join(out)


def relation_text(lines, kind):
    """类图/状态图/实体关系图转关系列表。"""
    out = []
    for raw in lines:
        s = raw.strip()
        low = s.lower()
        if not s or s.startswith("%%") or low == "end" or diagram_kind(low):
            continue
        if low.startswith("class "):
            out.append("类：%s" % s[6:].strip().rstrip("{").strip())
            continue
        if low.startswith("state "):
            out.append("状态：%s" % s[6:].strip().rstrip("{").strip())
            continue
        if s.startswith("}"):
            continue
        if kind == "erdiagram":
            m = re.match(r"^([\w\u4e00-\u9fff]+)\s*\{$", s)
            if m:
                out.append("实体：%s" % m.group(1))
                continue
            m = re.match(r"^([\w\u4e00-\u9fff]+)\s+([|}{o]+)-{1,2}([|}{o]+)\s+(\S+)\s*:\s*(.*)$", s)
            if m:
                out.append("%s %s 对 %s %s：%s" % (m.group(1), ER_CARD.get(m.group(2), m.group(2)),
                                                   ER_CARD.get(m.group(3), m.group(3)), m.group(4),
                                                   m.group(5).strip()))
                continue
            out.append("    · %s" % clean_node(s, set(), markdown=False))
            continue
        for token, name in REL_KINDS:
            if token not in s:
                continue
            if kind == "statediagram":
                name = "→"
            a, b = (x.strip() for x in s.split(token, 1))
            if name in ("继承", "实现") and token.startswith("<"):
                a, b = b, a
            label = ""
            if ":" in b:
                b, label = (x.strip() for x in b.split(":", 1))
            a = a.replace("[*]", "开始")
            b = b.replace("[*]", "结束")
            out.append("%s %s %s%s" % (a, name, b, ("：%s" % label) if label else ""))
            break
        else:
            out.append("    · %s" % clean_node(s, set(), markdown=False))
    return "\n".join(out)


def structured_text(lines, kind):
    """其它 mermaid 图类型转结构化编号文本。"""
    out = ["【%s】" % DIAGRAMS[kind]]
    n = 0
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("%%") or diagram_kind(s.lower()) == kind:
            continue
        n += 1
        out.append("%d. %s" % (n, s))
    return "\n".join(out)


def looks_like_mindmap(lines):
    """判断代码块是否真是 mindmap 结构。"""
    items = [x for x in lines if x.strip() and not x.strip().lower().startswith("mindmap")]
    if not items or len(items) > 200:
        return False
    if any("```" in x or HEAD_RE.match(x.strip()) for x in items):
        return False
    if any(looks_like_edge(x) for x in items):
        return False
    indented = sum(1 for x in items if x[:1] in (" ", "\t"))
    return indented >= len(items) - 1


def looks_like_flow(lines):
    """判断代码块是否真是流程图结构。"""
    body = [x.strip() for x in lines if x.strip()]
    if not body or len(body) > 200:
        return False
    return all(is_flow_line(x) or re.match(r"^[\w\u4e00-\u9fff]+\s*[\[\{\(]", x)
               or x.lower().startswith(FLOW_HEAD) for x in body)


def render_mermaid(lines, warnings, notes, label=""):
    """把 mermaid 代码转成文字，不是图表则返回 None。"""
    first = next((x.strip() for x in lines if x.strip()), "")
    low = first.lower()
    kind = diagram_kind(low)
    if label.lower() not in ("", "mermaid") and not kind \
            and not low.startswith(("mindmap", "graph", "flowchart")):
        return None
    if low.startswith("mindmap") and looks_like_mindmap(lines):
        return mermaid_to_tree(lines, warnings)
    if re.match(r"^(graph|flowchart)\b", low) and looks_like_flow(lines):
        return mermaid_to_flow(lines, warnings)
    if kind == "sequencediagram":
        return sequence_text(lines)
    if kind in ("classdiagram", "statediagram", "erdiagram"):
        return relation_text(lines, kind)
    if kind:
        return structured_text(lines, kind)
    body = [x for x in lines if x.strip()]
    # 围栏丢失时，裸露的连线段落也按流程图处理
    if not low.startswith(("mindmap", "graph", "flowchart")) \
            and any(looks_like_edge(x) for x in body) and looks_like_flow(body):
        return mermaid_to_flow(lines, warnings)
    if body:
        notes.add("mermaid_other")
        return "\n".join("%d. %s" % (k + 1, x.strip()) for k, x in enumerate(body))
    return None


def frame_block(lines, warnings, notes):
    """框架模式处理一个普通文本块。"""
    out = []
    fuzzy = FMT == 1
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        tb = match_pipe_table(lines, i)
        if tb:
            out.append(render_table(tb[0], warnings))
            i = tb[1]
            continue
        if fuzzy:
            mm = match_bare_mindmap(lines, i)
            if mm:
                out.append(mermaid_to_tree(mm[0], warnings))
                i = mm[1]
                continue
            ws = match_ws_table(lines, i)
            if ws:
                out.append(render_ws_table(ws[0], warnings))
                i = ws[1]
                continue
        if fuzzy and flow_run_start(stripped):
            run, j = collect_flow_run(lines, i)
            drawn = render_mermaid(run, warnings, notes)
            if drawn is not None:
                out.append(drawn)
                i = j
                continue
        m = HEAD_RE.match(stripped)
        if m:
            out.append("■ " + clean_node(m.group(2), warnings))
            i += 1
            continue
        m = LIST_RE.match(line)
        if m:
            items = []
            stack = []
            while i < n:
                depth, text = list_depth(lines[i])
                if depth is None or not lines[i].strip():
                    break
                while stack and depth < stack[-1]:
                    stack.pop()
                if not stack or depth > stack[-1]:
                    stack.append(depth)
                items.append((len(stack), task_mark(clean_node(text, warnings))))
                i += 1
            out.append("\n".join(tree_lines(items, root_bracket=False)))
            continue
        out.append(clean_node(stripped, warnings))
        i += 1
    return "\n".join(out)


def to_frame(text, warnings, notes):
    parts = []
    text = join_block_math(text)
    for kind, content, label in split_blocks(text):
        if kind == "code":
            lines = content.split("\n")
            drawn = render_mermaid(lines, warnings, notes, label)
            if drawn is None:
                parts.append(code_note(label))
                parts.append(content)
            else:
                parts.append(drawn)
        else:
            parts.append(frame_block(content.split("\n"), warnings, notes))
    return tighten("\n".join(parts))


# ---------------- 按输入格式分派 ----------------

ENV_BLOCK_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}(.*?)\\end\{\1\}", re.S)


def protect_envs(seg):
    """把裸环境整块渲染成多行占位，返回（占位文本，渲染列表）。"""
    rendered = []

    def repl(m):
        env, body = m.group(1), m.group(2)
        if env.rstrip("*") in ARG_ENVS:
            # 剥掉 array 一类的列格式参数
            body = re.sub(r"^\s*(?:\{[^{}]*\}|\[[^\]]*\])\s*", "", body, count=1)
        # 续行缩进取环境在本行已有的前文
        prefix = seg[:m.start()].rsplit("\n", 1)[-1]
        rendered.append(render_env(env, body, prefix))
        return "%s%d%s" % (ENV_MARK, len(rendered) - 1, ENV_MARK_END)

    return ENV_BLOCK_RE.sub(repl, seg), rendered


def restore_envs(text, rendered):
    """把占位还原为渲染好的多行环境文本。"""
    def repl(m):
        idx = int(m.group(1))
        return rendered[idx] if 0 <= idx < len(rendered) else m.group(0)
    return re.sub(r"%s(\d+)%s" % (ENV_MARK, ENV_MARK_END), repl, text)


def formula_text(text, warnings, notes):
    """公式为主：$ 段与裸环境按 LaTeX 转换，代码围栏原样保留。"""
    parts = []
    for kind, content, label in split_blocks(text):
        if kind == "code":
            parts.append(code_note(label))
            parts.append(content)
            continue
        segs = []
        for k, seg in split_math(join_block_math(content), warnings):
            if k == "math":
                segs.append(latex_to_plain(seg.strip(), "".join(segs).rsplit("\n", 1)[-1]))
                continue
            protected, rendered = protect_envs(seg)
            plain = convert_bare_latex(strip_emphasis(protected))
            segs.append(restore_envs(plain, rendered))
        parts.append("".join(segs))
    # 兜底清除未还原的占位符字符
    return tighten("\n".join(parts)).replace(ENV_MARK, "").replace(ENV_MARK_END, "")


def table_text(text, warnings, notes):
    """整段按表格处理，兼容管道表与空白对齐表。"""
    lines = [x for x in text.split("\n") if x.strip() and not PIPE_SEP_RE.match(x)]
    if not lines:
        return ""
    pipe = [x for x in lines if "|" in x]
    stray = ""
    cols = 0
    if pipe:
        cols = max(len(split_row(x)) for x in pipe)
        rows = [split_row(x) if "|" in x else split_ws_cells(x, cols) for x in lines]
    else:
        counts = {}
        for x in lines:
            counts[len(x.split())] = counts.get(len(x.split()), 0) + 1
        cols = max(counts, key=lambda c: (counts[c], c))
        rows = []
        for x in lines:
            toks = x.split()
            # 表头多出的前导词视为散文字，单独输出
            if not rows and len(toks) > cols:
                stray = " ".join(toks[:len(toks) - cols])
                toks = toks[-cols:]
            rows.append(toks if len(toks) <= cols else split_ws_cells(x, cols))
    if cols < 2:
        notes.add("no_table")
    table = render_cells([r for r in rows if any(r)], warnings)
    return (stray + "\n" + table).strip() if stray else table


def plain_text(text, warnings, notes):
    """纯文本：只去强调符号、转译公式，保留原缩进，不重建表格与脑图。"""
    parts = []
    for kind, content, label in split_blocks(text):
        if kind == "code":
            parts.append(code_note(label))
            parts.append(content)
            continue
        for line in join_block_math(content).split("\n"):
            parts.append(convert_inline(line, warnings, bare_math=True) if line.strip() else "")
    return tighten("\n".join(parts))


DIAGRAM_HEAD_RE = re.compile(r"^(mindmap|graph|flowchart|%s)\b" % "|".join(DIAGRAMS), re.I)


def is_diagram_seg(lines):
    """判断段落能否按 mindmap/graph/其它 mermaid 图类型渲染。"""
    first = next((x.strip() for x in lines if x.strip()), "")
    low = first.lower()
    if low.startswith("mindmap"):
        return looks_like_mindmap(lines)
    if re.match(r"^(graph|flowchart)\b", low):
        return looks_like_flow(lines)
    if diagram_kind(low):
        return True
    body = [x for x in lines if x.strip()]
    return bool(body) and any(looks_like_edge(x) for x in body) and looks_like_flow(body)


def diagram_text(text, warnings, notes):
    """图表代码：围栏块整块判定，无围栏文本按图表头分段，判不出的段原样输出。"""
    parts = []
    found = False
    for kind, content, label in split_blocks(text):
        lines = content.split("\n")
        if kind == "code":
            first = next((x.strip() for x in lines if x.strip()), "")
            if label.lower() in ("", "mermaid") or diagram_kind(first.lower()):
                drawn = render_mermaid(lines, warnings, notes, label)
                if drawn is not None:
                    parts.append(drawn)
                    found = True
                    continue
            parts.append(code_note(label))
            parts.append(content)
            continue
        drawn, hit = diagram_run(lines, warnings, notes)
        parts.append(drawn)
        found = found or hit
    if not found:
        notes.add("no_tree")
    return tighten("\n".join(parts))


def diagram_run(lines, warnings, notes):
    """无围栏文本按图表头切分渲染，其余行原样保留。"""
    out = []
    seg = []
    hit = False

    def flush():
        nonlocal hit
        if not any(x.strip() for x in seg):
            return
        best = 0
        for k in range(len(seg), 0, -1):
            if is_diagram_seg(seg[:k]):
                best = k
                break
        if best:
            out.append(render_mermaid(seg[:best], warnings, notes))
            hit = True
        tail = [x for x in (seg[best:] if best else seg) if x.strip()]
        if tail:
            out.append(tighten("\n".join(x.rstrip() for x in tail)))

    for line in lines:
        if DIAGRAM_HEAD_RE.match(line.strip()):
            flush()
            seg = [line]
            continue
        seg.append(line)
    flush()
    return "\n".join(x for x in out if x), hit


def convert(text, warnings, notes):
    """按所选输入格式分派转换路径。"""
    if FMT == 7:
        # 代码/结构化文本：字符已清洗，保留缩进与转义
        return text.rstrip("\n")
    if FMT == 6:
        # 公式：$ 段与裸公式、裸环境按 LaTeX 转换
        return formula_text(text, warnings, notes)
    if FMT == 5:
        # 思维导图：mermaid 全家族，绝不进表格渲染
        return diagram_text(text, warnings, notes)
    if FMT == 4:
        return table_text(text, warnings, notes)
    if FMT == 3:
        return plain_text(text, warnings, notes)
    # 1 自动识别与 2 Markdown 共用分块流程，模糊规则由 FMT 控制
    return to_frame(text, warnings, notes)


# ---------------- 统一输出 ----------------

def banner(title):
    line = "═" * 52
    print(line)
    print(" " + title + "  " + VERSION)
    print(line)


def print_notes(warnings, notes):
    msgs = []
    if "unclosed_code" in warnings:
        msgs.append(t("unclosed_code"))
    if "unclosed_formula" in warnings:
        msgs.append(t("unclosed_formula"))
    if "mermaid_other" in notes:
        msgs.append("未识别的 mermaid 图类型，已按原文行编号列出。" if LANG == "zh"
                    else "Unrecognized mermaid diagram type; original lines numbered instead.")
    if "no_tree" in notes:
        msgs.append(t("no_tree"))
    if "no_table" in notes:
        msgs.append(t("no_table"))
    if any(STATS.values()):
        msgs.append(t("cleanup").format(**STATS))
    if msgs:
        print()
        print(t("warn_head"))
        for msg in msgs:
            print("  ※ " + msg)


def main():
    global LANG
    reconfigure_stdio()
    for key in STATS:
        STATS[key] = 0
    # 语言尚未确定时先用中文文案提问
    print(T["zh"]["lang_menu"])
    try:
        lang = input("> ").strip()
    except EOFError:
        lang = ""
    LANG = "en" if lang == "2" else "zh"
    # 非空且非 1/2 的语言输入提示后按默认中文继续
    if lang and lang not in ("1", "2"):
        print("※ " + t("bad_lang"))
    banner(t("title"))
    ask_format()
    text = read_content()
    # 所有模式都清洗；代码格式保留转义原文，公式段不参与转义还原
    text = clean_text(text, decode=FMT != 7)
    if not text.strip():
        print()
        print(t("empty_in"))
        print()
        print("═" * 52)
        print(" " + t("done"))
        print("═" * 52)
        return
    warnings = set()
    notes = set()
    # 检测未闭合代码块
    blocks = split_blocks(text)
    if blocks and blocks[-1][0] == "code" and \
            not text.rstrip().endswith("```") and "```" in text:
        warnings.add("unclosed_code")
    body = convert(text, warnings, notes)
    banner(t("fmt_%d" % FMT))
    print()
    print(body)
    print_notes(warnings, notes)
    print()
    print("═" * 52)
    print(" " + t("done"))
    print("═" * 52)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as exc:
        try:
            print()
            print(t("err_generic").format(err=type(exc).__name__))
            print("═" * 52)
        except Exception:
            pass
    sys.exit(0)
