from tinycss2 import (
    parse_stylesheet,
    parse_stylesheet_bytes,
    parse_declaration_list,
    serialize,
)
from tinycss2.serializer import serialize_url
from tinycss2.ast import Node as TCSS2Node
from warc2zim.url_rewriting import ArticleUrlRewriter
from typing import Optional, Iterable, Union


class CSSRewriter:
    def __init__(self, css_url: str):
        self.url_rewriter = ArticleUrlRewriter(css_url)

    def rewrite(self, content: Union[str, bytes]) -> str:
        if isinstance(content, bytes):
            rules = parse_stylesheet_bytes(content)[0]
        else:
            rules = parse_stylesheet(content)
        self.process_list(rules)

        output = serialize(rules)
        return output

    def rewrite_inline(self, content: str) -> str:
        rules = parse_declaration_list(content)
        self.process_list(rules)
        output = serialize(rules)
        return output

    def process_list(self, components: Iterable[TCSS2Node]):
        if components:  # May be null
            for component in components:
                self.process(component)

    def process(self, component: TCSS2Node):
        if component.type in ("qualified-rule", "() block", "[] block", "{} block"):
            self.process_list(component.content)
        elif component.type == "function":
            if component.lower_name == "url":
                url_component = component.arguments[0]
                new_url = self.url_rewriter(url_component.value)
                url_component.value = new_url
                url_component.representation = f'"{serialize_url(new_url)}"'
            else:
                self.process_list(component.arguments)
        elif component.type == "at-rule":
            self.process_list(component.prelude)
            self.process_list(component.content)
        elif component.type == "declaration":
            self.process_list(component.value)
        elif component.type == "url":
            new_url = self.url_rewriter(component.value)
            component.value = new_url
            component.representation = f"url({serialize_url(new_url)})"
