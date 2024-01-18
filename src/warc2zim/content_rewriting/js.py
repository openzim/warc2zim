import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

TransformationRule = tuple[re.Pattern, Callable[[re.Match], str]]

# Regex used to check if we ar import or exporting things in the string
# ie : If we are a module
IMPORT_RX = re.compile(r"""^\s*?import\s*?[{"'*]""")
EXPORT_RX = re.compile(
    r"^\s*?export\s*?({([\s\w,$\n]+?)}[\s;]*|default|class)\s+", re.M
)

# The regex used to rewrite `import ...` in module code.
IMPORT_MATCH_RX = re.compile(
    r"""^\s*?import(?:['"\s]*(?:[\w*${}\s,]+from\s*)?['"\s]?['"\s])(?:.*?)['"\s]""",
)

# A sub regex used inside `import ...` rewrite to rewrite http url imported
IMPORT_HTTP_RX = re.compile(
    r"""(import(?:['"\s]*(?:[\w*${}\s,]+from\s*)?['"\s]?['"\s]))((?:https?|[./]).*?)(['"\s])""",
)

# This list of global variables we want to wrap.
# We will setup the wrap only if the js script use them.
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

GLOBALS_RX = re.compile(
    r"("
    + "|".join([r"(?:^|[^$.])\b" + x + r"\b(?:$|[^$])" for x in GLOBAL_OVERRIDES])
    + ")"
)


def create_js_rules() -> list[TransformationRule]:
    """
    This function create all the transformation rules.

    A transformation rule is a tuple (Regex, rewrite_function).
    If the regex match in the rewritten script, the corresponding match object will be
    passed to rewrite_function.
    The rewrite_function must all take a `opts` dictionnary which will be the opts
    passed to the `JsRewriter.rewrite` function.
    This is mostly as if we were calling `re.sub(regex, rewrite_function, script_text)`.

    The regex will be combined and will match any non overlaping text.
    So rule to match will be applyed, potentially preventing futher rules to match.
    """

    # This will replace `this` in code. The `_____WB$wombat$check$this$function_____`
    # will "see" with wombat and may return a "wrapper" around `this`
    this_rw = "_____WB$wombat$check$this$function_____(this)"

    # This will replace `location = `. This will "see" with wombat and set what have to
    # be set.
    check_loc = (
        "((self.__WB_check_loc && self.__WB_check_loc(location, arguments)) || "
        "{}).href = "
    )

    # This will replace `eval(...)`.
    eval_str = (
        "WB_wombat_runEval2((_______eval_arg, isGlobal) => { var ge = eval; return "
        "isGlobal ? ge(_______eval_arg) : "
        "eval(_______eval_arg); }).eval(this, (function() { return arguments })(),"
    )

    def m2str(function):
        """
        Call a rewrite_function with a string instead of a match object.
        A lot of rewrite function don't need the match object as they are working
        directly on text. This decorator can be used on rewrite_function taking a str.
        """

        def wrapper(m_object, _opts):
            return function(m_object[0])

        return wrapper

    def add_prefix(prefix):
        """
        Create a rewrite_function which add the `prefix` to the matching str.
        """

        @m2str
        def f(x):
            return prefix + x

        return f

    def replace_prefix_from(prefix, match):
        """
        Returns a function which replaces everything before `match` with `prefix`.
        """

        @m2str
        def f(x):
            match_index = x.index(match)
            if match_index == 0:
                return prefix
            return x[:match_index] + prefix

        return f

    def add_suffix(suffix):
        """
        Create a rewrite_function which add a `suffix` to the match str.
        The suffix is added only if the match is not preceded by `.` or `$`.
        """

        def f(m_object, _opts):
            offset = m_object.start()
            if offset > 0 and m_object.string[offset - 1] in ".$":
                return m_object[0]
            return m_object[0] + suffix

        return f

    def replace_this():
        """
        Create a rewrite_function replacing "this" by `this_rw` in the matching str.
        """

        @m2str
        def f(x):
            return x.replace("this", this_rw)

        return f

    def replace(src, target):
        """
        Create a rewrite_function replacing `src` by `target` in the matching str.
        """

        @m2str
        def f(x):
            return x.replace(src, target)

        return f

    def replace_this_non_prop():
        """
        Create a rewrite_function replacing "this" by `this_rw`.

        Replacement happen only if "this" is not a property of an object.
        """

        def f(m_object, _opts):
            offset = m_object.start()
            prev = m_object.string[offset - 1] if offset > 0 else ""
            if prev == "\n":
                return m_object[0].replace("this", ";" + this_rw)
            if prev not in ".$":
                return m_object[0].replace("this", this_rw)
            return m_object[0]

        return f

    def replace_import(src, target):
        """
        Create a rewrite_function replacing `src` by `target` in the matching str.

        This "replace" function is intended to be use to replace in `import ...` as it
        adds a `import.meta.url` if we are in a module.
        """

        def f(m_object, opts):
            return m_object[0].replace(src, target) + (
                "import.meta.url, " if opts and opts.get("isModule") else '"", '
            )

        return f

    return [
        # rewriting `eval(...)` - invocation
        (re.compile(r"(?:^|\s)\beval\s*\("), replace_prefix_from(eval_str, "eval")),
        # rewriting `x = eval` - no invocation
        (re.compile(r"[=]\s*\beval\b(?![(:.$])"), replace("eval", "self.eval")),
        # rewriting `.postMessage` -> `__WB_pmw(self).postMessage`
        (re.compile(r"\.postMessage\b\("), add_prefix(".__WB_pmw(self)")),
        # rewriting `location = ` to custom expression `(...).href =` assignement
        (
            re.compile(r"[^$.]?\s?\blocation\b\s*[=]\s*(?![\s\d=])"),
            add_suffix(check_loc),
        ),
        # rewriting `return this`
        (re.compile(r"\breturn\s+this\b\s*(?![\s\w.$])"), replace_this()),
        # rewriting `this.` special porperties access on new line, with ; perpended
        # if prev chars is `\n`, or if prev is not `.` or `$`, no semi
        (
            re.compile(
                rf"[^$.]\s?\bthis\b(?=(?:\.(?:{'|'.join(GLOBAL_OVERRIDES)})\b))"
            ),
            replace_this_non_prop(),
        ),
        # rewrite `= this` or `, this`
        (re.compile(r"[=,]\s*\bthis\b\s*(?![\s\w:.$])"), replace_this()),
        # rewrite `})(this_rw)`
        (re.compile(r"\}(?:\s*\))?\s*\(this\)"), replace_this()),
        # rewrite this in && or || expr
        (
            re.compile(r"[^|&][|&]{2}\s*this\b\s*(?![|\s&.$](?:[^|&]|$))"),
            replace_this(),
        ),
        # ignore `async import`.
        # As the rule will match first, it will prevent next rule matching `import` to
        # be apply to `async import`.
        (re.compile(r"async\s+import\s*\("), m2str(lambda x: x)),
        # esm dynamic import, if found, mark as module
        (
            re.compile(r"[^$.]\bimport\s*\("),
            replace_import("import", "____wb_rewrite_import__"),
        ),
    ]  # pyright: ignore


REWRITE_JS_RULES = create_js_rules()


class JsRewriter:
    """
    JsRewriter is in charge of rewriting the js code stored in our zim file.

    The main "input" is a list of rules, each rule being a tuple (regex,
    rewriting_function). We want to apply each rule to the content. But doing it blindly
    is counter-productive. It would means that we have to do N replacements (N == number
    of rules).
    To avoid that, we create one unique regex (`compiled_rule`) equivalent to
    `(regex0|regex1|regex2|...)` and we do only one replacement with this regex.
    When we have a match, we do N regex search to know which rules is corresponding
    and we apply the associated rewriting_function.
    """

    def __init__(
        self,
        url_rewriter: Callable[[str], str],
        extra_rules: Iterable[TransformationRule] | None = None,
    ):
        self.extra_rules = extra_rules or []
        self.first_buff = self._init_local_declaration(GLOBAL_OVERRIDES)
        self.last_buff = "\n}"
        self.url_rewriter = url_rewriter

    def _init_local_declaration(self, local_decls: Iterable[str]) -> str:
        """
        Create the prefix text to add at beginning of script.

        This will be added to script only if the script is using of the declaration in
        local_decls.
        """
        assign_func = "_____WB$wombat$assign$function_____"
        buffer = (
            f"var {assign_func} = function(name) "
            "{return (self._wb_wombat && self._wb_wombat.local_init && "
            "self._wb_wombat.local_init(name)) || self[name]; };\n"
            "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) "
            "{ this.__WB_source = obj; return this; } }\n{\n"
        )
        for decl in local_decls:
            buffer += f"""let {decl} = {assign_func}("{decl}");\n"""
        buffer += "let arguments;\n"
        return buffer + "\n"

    def _get_module_decl(self, local_decls: Iterable[str]) -> str:
        """
        Create the prefix text to add at beginning of module script.

        This will be added to script only if the script is a module script.
        """
        wb_module_decl_url = self.url_rewriter.from_normalized(
            "_zim_static/__wb_module_decl.js"
        )
        return (
            f"""import {{ {", ".join(local_decls)} }} from "{wb_module_decl_url}";\n"""
        )

    def _detect_is_module(self, text: str) -> bool:
        if "import" in text and IMPORT_RX.search(text):
            return True
        if "export" in text and EXPORT_RX.search(text):
            return True
        return False

    def rewrite(self, text: str, opts: dict[str, Any] | None = None) -> str:
        """
        Rewrite the js code in `text`.
        """
        opts = opts or {}
        if not opts.get("isModule"):
            opts["isModule"] = self._detect_is_module(text)

        rules = REWRITE_JS_RULES[:]

        if opts["isModule"]:
            rules.append(self._get_esm_import_rule())

        rules += self.extra_rules

        compiled_rules = self._compile_rules(rules)

        new_text = self.rewrite_content(text, compiled_rules, rules, opts)

        if opts["isModule"]:
            return self._get_module_decl(GLOBAL_OVERRIDES) + new_text

        if GLOBALS_RX.search(text):
            new_text = self.first_buff + new_text + self.last_buff

        if opts.get("inline", False):
            new_text = new_text.replace("\n", " ")

        return new_text

    def _get_esm_import_rule(self) -> TransformationRule:
        def rewrite_import():
            def func(m_object, _opts):
                def sub_funct(match):
                    return (
                        f"{match.group(1)}{self.url_rewriter(match.group(2))}"
                        f"{match.group(3)}"
                    )

                return IMPORT_HTTP_RX.sub(sub_funct, m_object[0])

            return func

        return (IMPORT_MATCH_RX, rewrite_import())  # pyright: ignore

    def _compile_rules(self, rules: Iterable[TransformationRule]) -> re.Pattern:
        """
        Compile all the regex of the rules into only one `compiled_rules` pattern
        """
        rx_buff = "|".join(f"({rule[0].pattern})" for rule in rules)
        return re.compile(f"(?:{rx_buff})", re.M)

    def rewrite_content(
        self,
        text: str,
        compiled_rules: re.Pattern,
        rules: list[TransformationRule],
        opts: Mapping[str, Any],
    ) -> str:
        """
        Apply the unique `compiled_rules` pattern and replace the content.
        """

        def replace(m_object):
            """
            This method search for the specific rule which have matched and apply it.
            """
            for i, rule in enumerate(rules, 1):
                if not m_object.group(i):
                    # THis is not the ith rules which match
                    continue
                result = rule[1](m_object, opts)  # pyright: ignore
                return result

        return compiled_rules.sub(replace, text)
