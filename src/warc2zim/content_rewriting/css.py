import re
from collections.abc import Iterable

from tinycss2 import (
    ast,
    parse_declaration_list,
    parse_stylesheet,
    parse_stylesheet_bytes,
    serialize,
)
from tinycss2.serializer import serialize_url

from warc2zim.constants import logger
from warc2zim.content_rewriting.rx_replacer import RxRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter


class FallbackRegexCssRewriter(RxRewriter):
    def __init__(self, url_rewriter: ArticleUrlRewriter, base_href: str | None):
        rules = [
            (
                re.compile(r"""url\((?P<quote>['"])?(?P<url>.+?)(?P=quote)(?<!\\)\)"""),
                lambda m_object, _opts: "".join(
                    [
                        "url(",
                        m_object["quote"],
                        url_rewriter(m_object["url"], base_href),
                        m_object["quote"],
                        ")",
                    ]
                ),
            )
        ]
        super().__init__(rules)


class CssRewriter:
    def __init__(self, url_rewriter: ArticleUrlRewriter, base_href: str | None):
        self.url_rewriter = url_rewriter
        self.base_href = base_href
        self.fallback_rewriter = FallbackRegexCssRewriter(url_rewriter, base_href)

    def rewrite(self, content: str | bytes) -> str:
        try:
            if isinstance(content, bytes):
                rules = parse_stylesheet_bytes(content)[0]
            else:
                rules = parse_stylesheet(content)
            self.process_list(rules)

            output = serialize(rules)
        except Exception:
            # If tinycss fail to parse css, it will generate a "Error" token.
            # Exception is raised at serialization time.
            # We try/catch the whole process to be sure anyway.
            logger.warning(
                (
                    "Css transformation fails. Fallback to regex rewriter.\n"
                    "Article path is %s"
                ),
                self.url_rewriter.article_url,
            )
            return self.fallback_rewriter.rewrite(content, {})
        return output

    def rewrite_inline(self, content: str) -> str:
        try:
            rules = parse_declaration_list(content)
            self.process_list(rules)
            output = serialize(rules)
            return output
        except Exception:
            # If tinycss fail to parse css, it will generate a "Error" token.
            # Exception is raised at serialization time.
            # We try/catch the whole process to be sure anyway.
            logger.warning(
                (
                    "Css transformation fails. Fallback to regex rewriter.\n"
                    "Content is `%s`"
                ),
                content,
            )
            return self.fallback_rewriter.rewrite(content, {})

    def process_list(self, components: Iterable[ast.Node]):
        if components:  # May be null
            for component in components:
                self.process(component)

    def process(self, component: ast.Node):
        if isinstance(
            component,
            ast.QualifiedRule
            | ast.SquareBracketsBlock
            | ast.ParenthesesBlock
            | ast.CurlyBracketsBlock,
        ):
            self.process_list(component.content)
        elif isinstance(component, ast.FunctionBlock):
            if component.lower_name == "url":
                url_component = component.arguments[0]
                new_url = self.url_rewriter(url_component.value, self.base_href)
                url_component.value = new_url
                url_component.representation = f'"{serialize_url(new_url)}"'
            else:
                self.process_list(component.arguments)
        elif isinstance(component, ast.AtRule):
            self.process_list(component.prelude)
            self.process_list(component.content)
        elif isinstance(component, ast.Declaration):
            self.process_list(component.value)
        elif isinstance(component, ast.URLToken):
            new_url = self.url_rewriter(component.value, self.base_href)
            component.value = new_url
            component.representation = f"url({serialize_url(new_url)})"
