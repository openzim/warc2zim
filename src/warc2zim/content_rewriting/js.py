import re
from typing import Any, Callable, Optional, Iterable, Tuple, Mapping, List

TransformationRule = Tuple[re.Pattern, Callable[[re.Match], str]]


IMPORT_RX = re.compile(r"""^\s*?import\s*?[{"'*]""")
EXPORT_RX = re.compile(
    r"^\s*?export\s*?({([\s\w,$\n]+?)}[\s;]*|default|class)\s+", re.M
)

IMPORT_MATCH_RX = re.compile(
    r"""^\s*?import(?:['"\s]*(?:[\w*${}\s,]+from\s*)?['"\s]?['"\s])(?:.*?)['"\s]""",
)

IMPORT_HTTP_RX = re.compile(
    r"""(import(?:['"\s]*(?:[\w*${}\s,]+from\s*)?['"\s]?['"\s]))((?:https?|[./]).*?)(['"\s])""",
)

GLOBAL_OVERRIDES = [
    "window",
    "globalThis",
    "self",
    "document",
    "location",
    "top",
    "parent",
    "frames",
    "opener",
]

GLOBALS_CONCAT_STR = "|".join(
    [r"(?:^|[^$.])\b" + x + r"\b(?:$|[^$])" for x in GLOBAL_OVERRIDES]
)

GLOBALS_RX = re.compile(r"(" + GLOBALS_CONCAT_STR + ")")


def createJSRules() -> List[TransformationRule]:
    thisRw = "_____WB$wombat$check$this$function_____(this)"
    checkLoc = "((self.__WB_check_loc && self.__WB_check_loc(location, arguments)) || {}).href = "
    evalStr = "WB_wombat_runEval2((_______eval_arg, isGlobal) => { var ge = eval; return isGlobal ? ge(_______eval_arg) : eval(_______eval_arg); }).eval(this, (function() { return arguments })(),"

    def m2str(function):
        def wrapper(m_object, opts):
            return function(m_object[0])

        return wrapper

    def addPrefix(prefix):
        @m2str
        def f(x):
            return prefix + x

        return f

    def replacePrefixFrom(prefix, match):
        @m2str
        def f(x):
            if x.index(match) == 0:
                return prefix
            else:
                return x[: x.index(match)] + prefix

        return f

    def addSuffix(suffix):
        def f(m_object, opts):
            offset = m_object.start()
            if offset > 0 and m_object.string[offset - 1] in ".$":
                return m_object[0]
            else:
                return m_object[0] + suffix

        return f

    def replaceThis():
        @m2str
        def f(x):
            return x.replace("this", thisRw)

        return f

    def replace(src, target):
        @m2str
        def f(x):
            return x.replace(src, target)

        return f

    def replaceThisProp():
        def f(m_object, opts):
            offset = m_object.start()
            prev = m_object.string[offset - 1] if offset > 0 else ""
            if prev == "\n":
                return m_object[0].replace("this", ";" + thisRw)
            elif prev not in ".$":
                return m_object[0].replace("this", thisRw)
            else:
                return m_object[0]

        return f

    def replaceImport(src, target):
        def f(m_object, opts):
            return m_object[0].replace(src, target) + (
                "import.meta.url, " if opts and opts.get("isModule") else '"", '
            )

        return f

    return [
        # rewriting `eval(...)` - invocation
        (re.compile(r"(?:^|\s)\beval\s*\("), replacePrefixFrom(evalStr, "eval")),
        # rewriting `x = eval` - no invocation
        (re.compile(r"[=]\s*\beval\b(?![(:.$])"), replace("eval", "self.eval")),
        # rewriting `.postMessage` -> `__WB_pmw(self).postMessage`
        (re.compile(r"\.postMessage\b\("), addPrefix(".__WB_pmw(self)")),
        # rewriting `location = ` to custom expression `(...).href =` assignement
        (re.compile(r"[^$.]?\s?\blocation\b\s*[=]\s*(?![\s\d=])"), addSuffix(checkLoc)),
        # rewriting `return this`
        (re.compile(r"\breturn\s+this\b\s*(?![\s\w.$])"), replaceThis()),
        # rewriting `this.` special porperties access on new line, with ; perpended
        # if prev chars is `\n`, or if prev is not `.` or `$`, no semi
        (
            re.compile(
                r"[^$.]\s?\bthis\b(?=(?:\.(?:{})\b))".format("|".join(GLOBAL_OVERRIDES))
            ),
            replaceThisProp(),
        ),
        # rewrite `= this` or `, this`
        (re.compile(r"[=,]\s*\bthis\b\s*(?![\s\w:.$])"), replaceThis()),
        # rewrite `})(thisRw)`
        (re.compile(r"\}(?:\s*\))?\s*\(this\)"), replaceThis()),
        # rewrite this in && or || expr
        (re.compile(r"[^|&][|&]{2}\s*this\b\s*(?![|\s&.$](?:[^|&]|$))"), replaceThis()),
        # ignore `async import`, custom function
        (re.compile(r"async\s+import\s*\("), m2str(lambda x: x)),
        # esm dynamic import, if found, mark as module
        (
            re.compile(r"[^$.]\bimport\s*\("),
            replaceImport("import", "____wb_rewrite_import__"),
        ),
    ]


class JsRewriter:
    def __init__(
        self,
        url_rewriter: Callable[[str], str],
        extraRules: Optional[Iterable[TransformationRule]] = None,
    ):
        self.extraRules = extraRules
        self.firstBuff = self.initLocalDeclaration(GLOBAL_OVERRIDES)
        self.lastBuff = "\n\n}"
        self.url_rewriter = url_rewriter

    def initLocalDeclaration(self, localDecls: Iterable[str]) -> str:
        ASSIGN_FUNC = "_____WB$wombat$assign$function_____"
        buffer = f"""var {ASSIGN_FUNC} = function(name) {{return (self._wb_wombat && self._wb_wombat.local_init && self._wb_wombat.local_init(name)) || self[name]; }};
if (!self.__WB_pmw) {{ self.__WB_pmw = function(obj) {{ this.__WB_source = obj; return this; }} }}
{{
"""
        for decl in localDecls:
            buffer += f"""let {decl} = {ASSIGN_FUNC}("{decl}");\n"""
        buffer += "let arguments;\n"
        return buffer + "\n"

    def getModuleDecl(self, localDecls: Iterable[str]) -> str:
        wb_module_decl_url = self.url_rewriter.from_normalized(
            "_zim_static/__wb_module_decl.js"
        )
        return (
            f"""import {{ {", ".join(localDecls)} }} from "{wb_module_decl_url}";\n"""
        )

    def detectIsModule(self, text: str) -> bool:
        if "import" in text and IMPORT_RX.search(text):
            return True
        if "export" in text and EXPORT_RX.search(text):
            return True
        return False

    def rewrite(self, text: str, opts: Mapping[str, Any] = None) -> str:
        opts = opts or {}
        if not opts.get("isModule"):
            opts["isModule"] = self.detectIsModule(text)

        rules = createJSRules()

        if opts["isModule"]:
            rules.append(self.getESMImportRule())

        if self.extraRules:
            rules += self.extraRules

        compiled_rules = self.compileRules(rules)

        newText = self.rewrite_content(text, compiled_rules, rules, opts)

        if opts["isModule"]:
            return self.getModuleDecl(GLOBAL_OVERRIDES) + newText

        wrapGlobals = GLOBALS_RX.search(text)

        if wrapGlobals:
            newText = self.firstBuff + newText + self.lastBuff

        if opts.get("inline", False):
            newText = newText.replace("\n", " ")

        return newText

    def getESMImportRule(self) -> TransformationRule:
        def rewriteImport():
            def func(m_object, opts):
                def sub_funct(match):
                    return f"{match.group(1)}{self.url_rewriter(match.group(2))}{match.group(3)}"

                return IMPORT_HTTP_RX.sub(sub_funct, m_object[0])

            return func

        return (IMPORT_MATCH_RX, rewriteImport())

    def compileRules(self, rules: Iterable[TransformationRule]) -> re.Pattern:
        rxBuff = ""

        for rule in rules:
            if rxBuff:
                rxBuff += "|"
            rxBuff += f"({rule[0].pattern})"

        rxString = f"(?:{rxBuff})"
        return re.compile(rxString, re.M)

    def rewrite_content(
        self,
        text: str,
        compiled_rules: re.Pattern,
        rules: List[TransformationRule],
        opts: Mapping[str, Any],
    ) -> str:
        def replace(m_object):
            for i, rule in enumerate(rules, 1):
                if not m_object.group(i):
                    # THis is not the ith rules which match
                    continue
                result = rule[1](m_object, opts)
                return result

        return compiled_rules.sub(replace, text)
