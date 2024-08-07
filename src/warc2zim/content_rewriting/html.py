import io
import re
from collections import namedtuple
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from html import escape
from html.parser import HTMLParser
from inspect import Signature, signature

from bs4 import BeautifulSoup

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, ZimPath

AttrNameAndValue = tuple[str, str | None]
AttrsList = list[AttrNameAndValue]

RewritenHtml = namedtuple("RewritenHmtl", ["title", "content"])

HTTP_EQUIV_REDIRECT_RE = re.compile(
    r"^\s*(?P<interval>.*?)\s*;\s*url\s*=\s*(?P<url>.*?)\s*$"
)


def get_attr_value_from(
    attrs: AttrsList, name: str, default: str | None = None
) -> str | None:
    """Get one HTML attribute value if present, else return default value"""
    for attr_name, value in attrs:
        if attr_name == name:
            return value
    return default


def format_attr(name: str, value: str | None) -> str:
    """Format a given attribute name and value, properly escaping the value"""
    if value is None:
        return name
    html_escaped_value = escape(value, quote=True)
    return f'{name}="{html_escaped_value}"'


def get_html_rewrite_context(tag: str, attrs: AttrsList) -> str:
    """Get current HTML rewrite context

    By default, rewrite context is the HTML tag. But in some cases (e.g. script tags) we
    need to be more precise since rewriting logic will vary based on another attribute
    value (e.g. type attribute for script tags)
    """
    if tag == "script":
        script_type = get_attr_value_from(attrs, "type")
        return {
            "application/json": "json",
            "json": "json",
            "module": "js-module",
            "application/javascript": "js-classic",
            "text/javascript": "js-classic",
            "": "js-classic",
        }.get(script_type or "", "unknown")
    elif tag == "link":
        link_rel = get_attr_value_from(attrs, "rel")
        if link_rel == "modulepreload":
            return "js-module"
        elif link_rel == "preload":
            preload_type = get_attr_value_from(attrs, "as")
            if preload_type == "script":
                return "js-classic"
    return tag


def extract_base_href(content: str) -> str | None:
    """Extract base href value from HTML content

    This is done in a specific function before real parsing / rewriting of any HTML
    because we need this information before rewriting any link since we might have stuff
    before the <base> tag in html head (e.g. <link> for favicons)
    """
    soup = BeautifulSoup(content, features="lxml")
    if not soup.head:
        return None
    for base in soup.head.find_all("base"):
        if base.has_attr("href"):
            return base["href"]
    return None


@cache
def _cached_signature(func: Callable) -> Signature:
    """Returns the signature of a given callable

    Result is cached to save performance when reused multiple times
    """
    return signature(func)


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

        self.base_href = extract_base_href(content)
        self.css_rewriter = CssRewriter(self.url_rewriter, self.base_href)
        self.js_rewriter = JsRewriter(
            url_rewriter=self.url_rewriter,
            base_href=self.base_href,
            notify_js_module=self.notify_js_module,
        )

        self.feed(content)
        self.close()

        output = self.output.getvalue()
        self.output = None
        return RewritenHtml(self.title or "", output)

    def send(self, value: str):
        self.output.write(value)  # pyright: ignore[reportOptionalMemberAccess]

    def handle_starttag(self, tag: str, attrs: AttrsList, *, auto_close: bool = False):
        self.html_rewrite_context = get_html_rewrite_context(tag=tag, attrs=attrs)

        if (
            rewritten := rules._do_tag_rewrite(
                tag=tag, attrs=attrs, auto_close=auto_close
            )
        ) is not None:
            self.send(rewritten)
            return

        self.send(f"<{tag}")
        if attrs:
            self.send(" ")
        self.send(
            " ".join(
                format_attr(*attr)
                for attr in (
                    rules._do_attribute_rewrite(
                        tag=tag,
                        attr_name=attr_name,
                        attr_value=attr_value,
                        attrs=attrs,
                        js_rewriter=self.js_rewriter,
                        css_rewriter=self.css_rewriter,
                        url_rewriter=self.url_rewriter,
                        base_href=self.base_href,
                        notify_js_module=self.notify_js_module,
                    )
                    for attr_name, attr_value in attrs
                    if not rules._do_drop_attribute(
                        tag=tag, attr_name=attr_name, attr_value=attr_value, attrs=attrs
                    )
                )
            )
        )

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
        if (
            data.strip()
            and (
                rewritten := rules._do_data_rewrite(
                    html_rewrite_context=self.html_rewrite_context,
                    data=data,
                    css_rewriter=self.css_rewriter,
                    js_rewriter=self.js_rewriter,
                    url_rewriter=self.url_rewriter,
                )
            )
            is not None
        ):
            self.send(rewritten)
            return
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


DropAttributeCallable = Callable[..., bool]
RewriteAttributeCallable = Callable[..., AttrNameAndValue | None]
RewriteTagCallable = Callable[..., str | None]
RewriteDataCallable = Callable[..., str | None]


@dataclass(frozen=True)
class DropAttributeRule:
    """A rule specifying when an HTML attribute should be dropped"""

    func: DropAttributeCallable


@dataclass(frozen=True)
class RewriteAttributeRule:
    """A rule specifying how a given HTML attribute should be rewritten"""

    func: RewriteAttributeCallable


@dataclass(frozen=True)
class RewriteTagRule:
    """A rule specifying how a given HTML tag should be rewritten"""

    func: RewriteTagCallable


@dataclass(frozen=True)
class RewriteDataRule:
    """A rule specifying how a given HTML data should be rewritten"""

    func: RewriteDataCallable


def _check_decorated_func_signature(expected_func: Callable, decorated_func: Callable):
    """Checks if the decorated function signature is compatible

    It checks that decorated function parameters have known names and proper types
    """
    expected_params = _cached_signature(expected_func).parameters
    func_params = _cached_signature(decorated_func).parameters
    for name, param in func_params.items():
        if name not in expected_params:
            raise TypeError(
                f"Parameter '{name}' is unsupported in function "
                f"'{decorated_func.__name__}'"
            )

        if expected_params[name].annotation != param.annotation:
            raise TypeError(
                f"Parameter '{name}' in function '{decorated_func.__name__}' must be of"
                f" type '{expected_params[name].annotation}'"
            )


class HTMLRewritingRules:
    """A class holding the definitions of all rules to rewrite HTML documents"""

    def __init__(self) -> None:
        self.drop_attribute_rules: set[DropAttributeRule] = set()
        self.rewrite_attribute_rules: set[RewriteAttributeRule] = set()
        self.rewrite_tag_rules: set[RewriteTagRule] = set()
        self.rewrite_data_rules: set[RewriteDataRule] = set()

    def drop_attribute(
        self,
    ) -> Callable[[DropAttributeCallable], DropAttributeCallable]:
        """Decorator to use when defining a rule regarding attribute dropping"""

        def decorator(func: DropAttributeCallable) -> DropAttributeCallable:
            _check_decorated_func_signature(self._do_drop_attribute, func)
            self.drop_attribute_rules.add(DropAttributeRule(func=func))
            return func

        return decorator

    def rewrite_attribute(
        self,
    ) -> Callable[[RewriteAttributeCallable], RewriteAttributeCallable]:
        """Decorator to use when defining a rule regarding attribute rewriting"""

        def decorator(func: RewriteAttributeCallable) -> RewriteAttributeCallable:
            _check_decorated_func_signature(self._do_attribute_rewrite, func)
            self.rewrite_attribute_rules.add(RewriteAttributeRule(func=func))
            return func

        return decorator

    def rewrite_tag(
        self,
    ) -> Callable[[RewriteTagCallable], RewriteTagCallable]:
        """Decorator to use when defining a rule regarding tag rewriting

        This has to be used when we need to rewrite the whole start tag. It can also
        handle rewrites of startend tags (autoclosing tags).
        """

        def decorator(func: RewriteTagCallable) -> RewriteTagCallable:
            _check_decorated_func_signature(self._do_tag_rewrite, func)
            self.rewrite_tag_rules.add(RewriteTagRule(func=func))
            return func

        return decorator

    def rewrite_data(
        self,
    ) -> Callable[[RewriteDataCallable], RewriteDataCallable]:
        """Decorator to use when defining a rule regarding data rewriting

        This has to be used when we need to rewrite the tag data.
        """

        def decorator(func: RewriteDataCallable) -> RewriteDataCallable:
            _check_decorated_func_signature(self._do_data_rewrite, func)
            self.rewrite_data_rules.add(RewriteDataRule(func=func))
            return func

        return decorator

    def _do_drop_attribute(
        self, tag: str, attr_name: str, attr_value: str | None, attrs: AttrsList
    ) -> bool:
        """Utility function to process all attribute dropping rules

        Returns true if at least one rule is matching
        """
        return any(
            rule.func(
                **{
                    arg_name: arg_value
                    for arg_name, arg_value in {
                        "tag": tag,
                        "attr_name": attr_name,
                        "attr_value": attr_value,
                        "attrs": attrs,
                    }.items()
                    if arg_name in _cached_signature(rule.func).parameters
                }
            )
            is True
            for rule in self.drop_attribute_rules
        )

    def _do_attribute_rewrite(
        self,
        tag: str,
        attr_name: str,
        attr_value: str | None,
        attrs: AttrsList,
        js_rewriter: JsRewriter,
        css_rewriter: CssRewriter,
        url_rewriter: ArticleUrlRewriter,
        base_href: str | None,
        notify_js_module: Callable[[ZimPath], None],
    ) -> AttrNameAndValue:
        """Utility function to process all attribute rewriting rules

        Returns the rewritten attribute name and value
        """

        if attr_value is None:
            return attr_name, None

        for rule in self.rewrite_attribute_rules:
            if (
                rewritten := rule.func(
                    **{
                        arg_name: arg_value
                        for arg_name, arg_value in {
                            "tag": tag,
                            "attr_name": attr_name,
                            "attr_value": attr_value,
                            "attrs": attrs,
                            "js_rewriter": js_rewriter,
                            "css_rewriter": css_rewriter,
                            "url_rewriter": url_rewriter,
                            "base_href": base_href,
                            "notify_js_module": notify_js_module,
                        }.items()
                        if arg_name in _cached_signature(rule.func).parameters
                    }
                )
            ) is not None:
                attr_name, attr_value = rewritten

        return attr_name, attr_value

    def _do_tag_rewrite(
        self,
        tag: str,
        attrs: AttrsList,
        *,
        auto_close: bool,
    ) -> str | None:
        """Utility function to process all tag rewriting rules

        Returns the rewritten tag
        """

        for rule in self.rewrite_tag_rules:
            if (
                rewritten := rule.func(
                    **{
                        arg_name: arg_value
                        for arg_name, arg_value in {
                            "tag": tag,
                            "attrs": attrs,
                            "auto_close": auto_close,
                        }.items()
                        if arg_name in _cached_signature(rule.func).parameters
                    }
                )
            ) is not None:
                return rewritten

    def _do_data_rewrite(
        self,
        html_rewrite_context: str | None,
        data: str,
        css_rewriter: CssRewriter,
        js_rewriter: JsRewriter,
        url_rewriter: ArticleUrlRewriter,
    ) -> str | None:
        """Utility function to process all data rewriting rules

        Returns the rewritten data
        """

        for rule in self.rewrite_data_rules:
            if (
                rewritten := rule.func(
                    **{
                        arg_name: arg_value
                        for arg_name, arg_value in {
                            "html_rewrite_context": html_rewrite_context,
                            "data": data,
                            "css_rewriter": css_rewriter,
                            "js_rewriter": js_rewriter,
                            "url_rewriter": url_rewriter,
                        }.items()
                        if arg_name in _cached_signature(rule.func).parameters
                    }
                )
            ) is not None:
                return rewritten


rules = HTMLRewritingRules()


@rules.drop_attribute()
def drop_script_integrity_attribute(tag: str, attr_name: str):
    """Drop integrity attribute in <script> tags"""
    return tag == "script" and attr_name == "integrity"


@rules.drop_attribute()
def drop_link_integrity_attribute(tag: str, attr_name: str):
    """Drop integrity attribute in <link> tags"""
    return tag == "link" and attr_name == "integrity"


@rules.rewrite_attribute()
def rewrite_meta_charset_content(
    tag: str, attr_name: str, attrs: AttrsList
) -> AttrNameAndValue | None:
    """Rewrite charset indicated in meta tag

    We need to rewrite both <meta charset='xxx'> and
    <meta http-equiv='content-type' content='text/html; charset=xxx'>
    """
    if tag != "meta":
        return
    if attr_name == "charset":
        return (attr_name, "UTF-8")
    if attr_name == "content" and any(
        attr_name.lower() == "http-equiv"
        and attr_value
        and attr_value.lower() == "content-type"
        for attr_name, attr_value in attrs
    ):
        return (attr_name, "text/html; charset=UTF-8")


@rules.rewrite_attribute()
def rewrite_onxxx_tags(
    attr_name: str, attr_value: str | None, js_rewriter: JsRewriter
) -> AttrNameAndValue | None:
    """Rewrite onxxx script attributes"""
    if attr_value and attr_name.startswith("on") and not attr_name.startswith("on-"):
        return (attr_name, js_rewriter.rewrite(attr_value))


@rules.rewrite_attribute()
def rewrite_style_tags(
    attr_name: str, attr_value: str | None, css_rewriter: CssRewriter
) -> AttrNameAndValue | None:
    """Rewrite style attributes"""
    if attr_value and attr_name == "style":
        return (attr_name, css_rewriter.rewrite_inline(attr_value))


@rules.rewrite_attribute()
def rewrite_href_src_attributes(
    tag: str,
    attr_name: str,
    attr_value: str | None,
    attrs: AttrsList,
    url_rewriter: ArticleUrlRewriter,
    base_href: str | None,
    notify_js_module: Callable[[ZimPath], None],
):
    """Rewrite href and src attributes

    This is also notifying of any JS script found used as a module, so that this script
    is properly rewritten when encountered later on.
    """
    if attr_name not in ("href", "src") or not attr_value:
        return
    if get_html_rewrite_context(tag=tag, attrs=attrs) == "js-module":
        notify_js_module(url_rewriter.get_item_path(attr_value, base_href=base_href))
    return (
        attr_name,
        url_rewriter(attr_value, base_href=base_href, rewrite_all_url=tag != "a"),
    )


@rules.rewrite_attribute()
def rewrite_srcset_attribute(
    attr_name: str,
    attr_value: str | None,
    url_rewriter: ArticleUrlRewriter,
    base_href: str | None,
):
    """Rewrite srcset attributes"""
    if attr_name != "srcset" or not attr_value:
        return
    value_list = attr_value.split(",")
    new_value_list = []
    for value in value_list:
        url, *other = value.strip().split(" ", maxsplit=1)
        new_url = url_rewriter(url, base_href=base_href)
        new_value = " ".join([new_url, *other])
        new_value_list.append(new_value)
    return (attr_name, ", ".join(new_value_list))


@rules.rewrite_tag()
def rewrite_base_tag(tag: str, attrs: AttrsList, *, auto_close: bool):
    """Handle special case of <base> tag which have to be simplified (remove href)

    This is special because resulting tag might be empty and hence needs to be dropped
    """
    if tag != "base":
        return
    if get_attr_value_from(attrs, "href") is None:
        return  # needed so that other rules will be processed as well
    values = " ".join(
        format_attr(*attr)
        for attr in [
            (attr_name, attr_value)
            for (attr_name, attr_value) in attrs
            if attr_name != "href"
        ]
    )
    if values:
        return f"<base {values}{'/>' if auto_close else '>'}"
    else:
        return ""  # drop whole tag


@rules.rewrite_data()
def rewrite_css_data(
    html_rewrite_context: str | None, data: str, css_rewriter: CssRewriter
) -> str | None:
    """Rewrite inline CSS"""
    if html_rewrite_context != "style":
        return
    return css_rewriter.rewrite(data)


@rules.rewrite_data()
def rewrite_json_data(
    html_rewrite_context: str | None,
) -> str | None:
    """Rewrite inline JSON"""
    if html_rewrite_context != "json":
        return
    # we do not have any JSON rewriting left ATM since all these rules are applied in
    # Browsertrix crawler before storing the WARC record for now
    return


@rules.rewrite_data()
def rewrite_js_data(
    html_rewrite_context: str | None,
    data: str,
    js_rewriter: JsRewriter,
) -> str | None:
    """Rewrite inline JS"""
    if not (html_rewrite_context and html_rewrite_context.startswith("js-")):
        return
    return js_rewriter.rewrite(
        data,
        opts={"isModule": html_rewrite_context == "js-module"},
    )


@rules.rewrite_attribute()
def rewrite_meta_http_equiv_redirect(
    tag: str,
    attr_name: str,
    attr_value: str | None,
    attrs: AttrsList,
    url_rewriter: ArticleUrlRewriter,
    base_href: str | None,
) -> AttrNameAndValue | None:
    """Rewrite redirect URL in meta http-equiv refresh"""
    if tag != "meta":
        return
    if attr_name != "content":
        return
    if not attr_value:
        return
    http_equiv = get_attr_value_from(attrs, "http-equiv")
    if http_equiv != "refresh":
        return
    if (match := HTTP_EQUIV_REDIRECT_RE.match(attr_value)) is None:
        return
    return (
        attr_name,
        f"{match['interval']};url={url_rewriter(match['url'], base_href=base_href)}",
    )
