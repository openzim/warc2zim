import io
from collections import namedtuple
from collections.abc import Callable
from html import escape
from html.parser import HTMLParser

from warc2zim.content_rewriting import UrlRewriterProto
from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.ds import get_ds_rules
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.content_rewriting.rx_replacer import RxRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, ZimPath

AttrsList = list[tuple[str, str | None]]

RewritenHtml = namedtuple("RewritenHmtl", ["title", "content"])


class HtmlRewriter(HTMLParser):
    def __init__(
        self,
        url_rewriter: ArticleUrlRewriter,
        pre_head_insert: str,
        post_head_insert: str | None,
        notify_js_module: Callable[[ZimPath], None],
    ):
        super().__init__(convert_charrefs=False)
        self.url_rewriter = url_rewriter
        self.css_rewriter = CssRewriter(url_rewriter)
        self.title = None
        self.output = None
        # This works only for tag without children.
        # But as we use it to get the title, we are ok
        self.html_rewrite_context = None
        self.pre_head_insert = pre_head_insert
        self.post_head_insert = post_head_insert
        self.notify_js_module = notify_js_module

    def rewrite(self, content: str) -> RewritenHtml:
        if self.output is not None:
            raise Exception("ouput should not already be set")  # pragma: no cover
        self.output = io.StringIO()

        self.feed(content)
        self.close()

        output = self.output.getvalue()
        self.output = None
        return RewritenHtml(self.title or "", output)

    def send(self, value: str):
        self.output.write(value)  # pyright: ignore[reportOptionalMemberAccess]

    def handle_starttag(self, tag: str, attrs: AttrsList, *, auto_close: bool = False):
        if tag == "script":
            script_type = self.extract_attr(attrs, "type")
            if script_type == "json":
                self.html_rewrite_context = "json"
            elif script_type == "module":
                self.html_rewrite_context = "js-module"
            else:
                self.html_rewrite_context = "js-classic"
        elif tag == "link":
            self.html_rewrite_context = "link"
            link_rel = self.extract_attr(attrs, "rel")
            if link_rel == "modulepreload":
                self.html_rewrite_context = "js-module"
            elif link_rel == "preload":
                preload_type = self.extract_attr(attrs, "as")
                if preload_type == "script":
                    self.html_rewrite_context = "js-classic"
        else:
            self.html_rewrite_context = tag

        self.send(f"<{tag}")
        if attrs:
            self.send(" ")
        if tag == "a":
            url_rewriter = lambda url: self.url_rewriter(  # noqa: E731
                url, rewrite_all_url=False
            )
        else:
            url_rewriter = self.url_rewriter
        self.send(self.transform_attrs(attrs, url_rewriter))

        if auto_close:
            self.send(" />")
        else:
            self.send(">")
        if tag == "head" and self.pre_head_insert:
            self.send(self.pre_head_insert)

    def handle_endtag(self, tag: str):
        self.html_rewrite_context = None
        if tag == "head" and self.post_head_insert:
            self.send(self.post_head_insert)
        self.send(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: AttrsList):
        self.handle_starttag(tag, attrs, auto_close=True)
        self.html_rewrite_context = None

    def handle_data(self, data: str):
        if self.html_rewrite_context == "title" and self.title is None:
            self.title = data.strip()
        elif self.html_rewrite_context == "style":
            data = self.css_rewriter.rewrite(data)
        elif self.html_rewrite_context and self.html_rewrite_context.startswith("js-"):
            if data.strip():
                data = JsRewriter(
                    url_rewriter=self.url_rewriter,
                    extra_rules=get_ds_rules(self.url_rewriter.article_url.value),
                    notify_js_module=self.notify_js_module,
                ).rewrite(
                    data,
                    opts={"isModule": self.html_rewrite_context == "js-module"},
                )
        elif self.html_rewrite_context == "json":
            if data.strip():
                rules = get_ds_rules(self.url_rewriter.article_url.value)
                if rules:
                    data = RxRewriter(rules).rewrite(data, {})
        self.send(data)

    def handle_entityref(self, name: str):
        self.send(f"&{name};")

    def handle_charref(self, name: str):
        self.send(f"&#{name};")

    def handle_comment(self, data: str):
        self.send(f"<!--{data}-->")

    def handle_decl(self, decl: str):
        self.send(f"<!{decl}>")

    def handle_pi(self, data: str):
        self.send(f"<?{data}>")

    def unknown_decl(self, data: str):
        self.handle_decl(data)

    def process_attr(
        self,
        attr: tuple[str, str | None],
        url_rewriter: UrlRewriterProto,
    ) -> tuple[str, str | None]:
        if not attr[1]:
            return attr

        if attr[0] in ("href", "src"):
            if self.html_rewrite_context == "js-module":
                self.notify_js_module(self.url_rewriter.get_item_path(attr[1]))
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
            return (attr[0], self.css_rewriter.rewrite_inline(attr[1]))
        return attr

    def format_attr(self, name: str, value: str | None) -> str:
        if value is None:
            return name
        html_escaped_value = escape(value, quote=True)
        return f'{name}="{html_escaped_value}"'

    def transform_attrs(
        self,
        attrs: AttrsList,
        url_rewriter: UrlRewriterProto,
    ) -> str:
        processed_attrs = (self.process_attr(attr, url_rewriter) for attr in attrs)
        return " ".join(self.format_attr(*attr) for attr in processed_attrs)

    def extract_attr(
        self, attrs: AttrsList, name: str, default: str | None = None
    ) -> str | None:
        for attr_name, value in attrs:
            if attr_name == name:
                return value
        return default
