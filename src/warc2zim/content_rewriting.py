from html import escape
from html.parser import HTMLParser
from tinycss2 import (
    parse_stylesheet,
    parse_stylesheet_bytes,
    parse_declaration_list,
    serialize,
)
from tinycss2.serializer import serialize_url
from tinycss2.ast import Node as TCSS2Node
import io
from collections import namedtuple
from warc2zim.url_rewriting import ArticleUrlRewriter
from warc2zim.utils import to_string
from typing import Callable, Optional, Iterable, List, Tuple, Union

AttrsList = List[Tuple[str, Optional[str]]]


def process_attr(
    attr: Tuple[str, Optional[str]],
    url_rewriter: Callable[[str], str],
    css_rewriter: "CssRewriter",
) -> Tuple[str, Optional[str]]:
    if attr[0] in ("href", "src"):
        return (attr[0], url_rewriter(attr[1]))
    if attr[0] == "srcset":
        value_list = attr[1].split(",")
        new_value_list = []
        for value in value_list:
            url, *other = value.strip().split(" ", maxsplit=1)
            new_url = url_rewriter(url)
            new_value = " ".join([new_url, *other])
            new_value_list.append(new_value)
        return (attr[0], ", ".join(new_value_list))
    if attr[0] == "style":
        return (attr[0], css_rewriter.rewrite_inline(attr[1]))
    return attr


def format_attr(name: str, value: Optional[str]) -> str:
    if value is None:
        return name
    html_escaped_value = escape(value, quote=True)
    return f'{name}="{html_escaped_value}"'


def transform_attrs(
    attrs: AttrsList, url_rewriter: Callable[[str], str], css_rewriter: "CssRewriter"
) -> str:
    processed_attrs = (process_attr(attr, url_rewriter, css_rewriter) for attr in attrs)
    return " ".join(format_attr(*attr) for attr in processed_attrs)


RewritenHtml = namedtuple("RewritenHmtl", ["title", "content"])


class HtmlRewriter(HTMLParser):
    def __init__(self, article_url: str, pre_head_insert: str, post_head_insert: str):
        super().__init__()
        self.url_rewriter = ArticleUrlRewriter(article_url)
        self.css_rewriter = CSSRewriter(article_url)
        self.title = None
        self.output = None
        # This works only for tag without children.
        # But as we use it to get the title, we are ok
        self._active_tag = None
        self.pre_head_insert = pre_head_insert
        self.post_head_insert = post_head_insert

    def rewrite(self, content: Union[str, bytes]) -> RewritenHtml:
        assert self.output == None
        self.output = io.StringIO()

        content = to_string(content)

        self.feed(content)
        self.close()

        output = self.output.getvalue()
        self.output = None
        return RewritenHtml(self.title or "", output)

    def send(self, value: str):
        self.output.write(value)

    def handle_starttag(self, tag: str, attrs: AttrsList, auto_close: bool = False):
        self._active_tag = tag

        self.send(f"<{tag}")
        if attrs:
            self.send(" ")
        self.send(transform_attrs(attrs, self.url_rewriter, self.css_rewriter))

        if auto_close:
            self.send(" />")
        else:
            self.send(">")
        if tag == "head" and self.pre_head_insert:
            self.send(self.pre_head_insert)

    def handle_endtag(self, tag: str):
        self._active_tag = None
        if tag == "head" and self.post_head_insert:
            self.send(self.post_head_insert)
        self.send(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: AttrsList):
        self.handle_starttag(tag, attrs, auto_close=True)
        self._active_tag = None

    def handle_data(self, data: str):
        if self._active_tag == "title" and self.title is None:
            self.title = data.strip()
        elif self._active_tag == "style":
            data = self.css_rewriter.rewrite(data)
        self.send(data)

    def handle_comment(self, data: str):
        self.send(f"<!--{data}-->")

    def handle_decl(self, decl: str):
        self.send(f"<!{decl}>")

    def handle_pi(self, data: str):
        self.send(f"<?{data}>")

    def unknown_decl(self, data: str):
        self.handle_decl(data)


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
        match component.type:
            case "qualified-rule" | "() block" | "[] block" | "{} block":
                self.process_list(component.content)
            case "function":
                if component.lower_name == "url":
                    url_component = component.arguments[0]
                    new_url = self.url_rewriter(url_component.value)
                    url_component.value = new_url
                    url_component.representation = f'"{serialize_url(new_url)}"'
                else:
                    self.process_list(component.arguments)
            case "at-rule":
                self.process_list(component.prelude)
                self.process_list(component.content)
            case "declaration":
                self.process_list(component.value)
            case "url":
                new_url = self.url_rewriter(component.value)
                component.value = new_url
                component.representation = f"url({serialize_url(new_url)})"
