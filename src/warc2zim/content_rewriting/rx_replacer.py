import re
from collections.abc import Callable, Iterable
from typing import Any

TransformationAction = Callable[[re.Match, dict], str]
TransformationRule = tuple[re.Pattern, TransformationAction]


def m2str(function) -> TransformationAction:
    """
    Call a rewrite_function with a string instead of a match object.
    A lot of rewrite function don't need the match object as they are working
    directly on text. This decorator can be used on rewrite_function taking a str.
    """

    def wrapper(m_object: re.Match, _opts: dict) -> str:
        return function(m_object[0])

    return wrapper


def add_around(prefix: str, suffix: str) -> TransformationAction:
    """
    Create a rewrite_function which add a `prefix` and a `suffix` around the match.
    """

    @m2str
    def f(x):
        return prefix + x + suffix

    return f


def add_prefix(prefix: str) -> TransformationAction:
    """
    Create a rewrite_function which add the `prefix` to the matching str.
    """

    return add_around(prefix, "")


def add_suffix(suffix: str) -> TransformationAction:
    """
    Create a rewrite_function which add the `suffix` to the matching str.
    """

    return add_around("", suffix)


def replace_prefix_from(prefix: str, match: str) -> TransformationAction:
    """
    Returns a function which replaces everything before `match` with `prefix`.
    """

    @m2str
    def f(x) -> str:
        match_index = x.index(match)
        if match_index == 0:
            return prefix
        return x[:match_index] + prefix

    return f


def replace(src, target) -> TransformationAction:
    """
    Create a rewrite_function replacing `src` by `target` in the matching str.
    """

    @m2str
    def f(x):
        return x.replace(src, target)

    return f


def replace_all(text: str) -> TransformationAction:
    """
    Create a rewrite_function which replace the whole match with text.
    """

    @m2str
    def f(_x):
        return text

    return f


class RxRewriter:
    """
    RxRewriter is a generic rewriter base on regex.

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
        rules: Iterable[TransformationRule] | None = None,
    ):
        self.rules = rules or []
        self.compiled_rule: re.Pattern | None = None
        if self.rules:
            self._compile_rules(self.rules)

    def _compile_rules(self, rules: Iterable[TransformationRule]):
        """
        Compile all the regex of the rules into only one `compiled_rules` pattern
        """
        self.rules = rules
        rx_buff = "|".join(f"({rule[0].pattern})" for rule in rules)
        self.compiled_rule = re.compile(f"(?:{rx_buff})", re.M)

    def rewrite(
        self,
        text: str | bytes,
        opts: dict[str, Any],
    ) -> str:
        """
        Apply the unique `compiled_rules` pattern and replace the content.
        """
        if isinstance(text, bytes):
            text = text.decode()

        def replace(m_object):
            """
            This method search for the specific rule which have matched and apply it.
            """
            for i, rule in enumerate(self.rules, 1):
                if not m_object.group(i):
                    # THis is not the ith rules which match
                    continue
                result = rule[1](m_object, opts)
                return result

        assert self.compiled_rule is not None  # noqa
        return self.compiled_rule.sub(replace, text)
