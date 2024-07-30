from collections.abc import Callable
from textwrap import dedent

import pytest

from warc2zim.content_rewriting.html import (
    AttrNameAndValue,
    AttrsList,
    HtmlRewriter,
    HTMLRewritingRules,
    extract_base_href,
    format_attr,
    get_attr_value_from,
    rewrite_meta_http_equiv_redirect,
)
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath

from .utils import ContentForTests


@pytest.fixture(
    params=[
        ContentForTests("A simple string without url"),
        ContentForTests(
            "<html><body><p>This is a sentence with a http://exemple.com/path link</p>"
            "</body></html>"
        ),
        ContentForTests(
            '<a data-source="http://exemple.com/path">A link we should not rewrite</a>'
        ),
        ContentForTests(
            '<p style="background: url(some/image.png);">A url (relative) in a inline '
            "style</p>"
        ),
        ContentForTests("<p style></p>"),
        ContentForTests(
            "<style>p { /* A comment with a http://link.org/ */ "
            'background: url("some/image.png") ; }</style>'
        ),
        ContentForTests("<a href></a>"),
        ContentForTests(
            """<a type="a&quot;type">This is a sample attribute with a quote in its"""
            "value and which is not a URL</a>"
        ),
        ContentForTests("<img src />"),
        ContentForTests("<code>&lt;script&gt;</code>"),
        ContentForTests(
            "<p> This is a smiley (🙂) and it html hex value (&#x1F642;) </p>"
        ),
        ContentForTests(
            '<script type="json">{"window": "https://kiwix.org/path"}</script>'
        ),
        ContentForTests(
            '<script type="application/json">{"window": "https://kiwix.org/path"}'
            "</script>"
        ),
        ContentForTests(
            '<script type="application/i_dont_know_you">'
            '{"window": "https://kiwix.org/path"}</script>'
        ),
    ]
)
def no_rewrite_content(request):
    yield request.param


def test_no_rewrite(no_rewrite_content, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{no_rewrite_content.article_url}"), set()
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(no_rewrite_content.input_str)
        .content
        == no_rewrite_content.expected_str
    )


@pytest.fixture(
    params=[
        ContentForTests(
            "<p style='background: url(\"some/image.png\")'>A link in a inline style"
            "</p>",
            '<p style="background: url(&quot;some/image.png&quot;);">'
            "A link in a inline style</p>",
        ),
        ContentForTests(
            "<p style=\"background: url('some/image.png')\">"
            "A link in a inline style</p>",
            '<p style="background: url(&quot;some/image.png&quot;);">'
            "A link in a inline style</p>",
        ),
        ContentForTests(
            "<ul style='list-style: \">\"'>",
            '<ul style="list-style: &quot;&gt;&quot;;">',
        ),
    ]
)
def escaped_content(request):
    yield request.param


def test_escaped_content(escaped_content, no_js_notify):
    transformed = (
        HtmlRewriter(
            ArticleUrlRewriter(HttpUrl(f"http://{escaped_content.article_url}"), set()),
            "",
            "",
            no_js_notify,
        )
        .rewrite(escaped_content.input_str)
        .content
    )
    assert transformed == escaped_content.expected_str


@pytest.fixture(
    params=[
        ContentForTests(
            '<script>document.title="HELLO";</script>',
            (
                "<script>var _____WB$wombat$assign$function_____ = function(name) "
                "{return (self._wb_wombat && self._wb_wombat.local_init && "
                "self._wb_wombat.local_init(name)) || self[name]; };\n"
                "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) "
                "{ this.__WB_source = obj; return this; } }\n"
                "{\n"
                """let window = _____WB$wombat$assign$function_____("window");\n"""
                "let globalThis = _____WB$wombat$assign$function_____"
                """("globalThis");\n"""
                """let self = _____WB$wombat$assign$function_____("self");\n"""
                """let document = _____WB$wombat$assign$function_____("document");\n"""
                """let location = _____WB$wombat$assign$function_____("location");\n"""
                """let top = _____WB$wombat$assign$function_____("top");\n"""
                """let parent = _____WB$wombat$assign$function_____("parent");\n"""
                """let frames = _____WB$wombat$assign$function_____("frames");\n"""
                """let opener = _____WB$wombat$assign$function_____("opener");\n"""
                "let arguments;\n\n"
                """document.title="HELLO";\n"""
                "}</script>"
            ),
        ),
        ContentForTests(
            '<script type="application/javascript">document.title="HELLO";</script>',
            (
                """<script type="application/javascript">"""
                "var _____WB$wombat$assign$function_____ = function(name) "
                ""
                "{return (self._wb_wombat && self._wb_wombat.local_init && "
                "self._wb_wombat.local_init(name)) || self[name]; };\n"
                "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) "
                "{ this.__WB_source = obj; return this; } }\n"
                "{\n"
                """let window = _____WB$wombat$assign$function_____("window");\n"""
                "let globalThis = _____WB$wombat$assign$function_____"
                """("globalThis");\n"""
                """let self = _____WB$wombat$assign$function_____("self");\n"""
                """let document = _____WB$wombat$assign$function_____("document");\n"""
                """let location = _____WB$wombat$assign$function_____("location");\n"""
                """let top = _____WB$wombat$assign$function_____("top");\n"""
                """let parent = _____WB$wombat$assign$function_____("parent");\n"""
                """let frames = _____WB$wombat$assign$function_____("frames");\n"""
                """let opener = _____WB$wombat$assign$function_____("opener");\n"""
                "let arguments;\n\n"
                """document.title="HELLO";\n"""
                "}</script>"
            ),
        ),
        ContentForTests(
            '<script type="text/javascript">document.title="HELLO";</script>',
            (
                """<script type="text/javascript">"""
                "var _____WB$wombat$assign$function_____ = function(name) "
                "{return (self._wb_wombat && self._wb_wombat.local_init && "
                "self._wb_wombat.local_init(name)) || self[name]; };\n"
                "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) "
                "{ this.__WB_source = obj; return this; } }\n"
                "{\n"
                """let window = _____WB$wombat$assign$function_____("window");\n"""
                "let globalThis = _____WB$wombat$assign$function_____"
                """("globalThis");\n"""
                """let self = _____WB$wombat$assign$function_____("self");\n"""
                """let document = _____WB$wombat$assign$function_____("document");\n"""
                """let location = _____WB$wombat$assign$function_____("location");\n"""
                """let top = _____WB$wombat$assign$function_____("top");\n"""
                """let parent = _____WB$wombat$assign$function_____("parent");\n"""
                """let frames = _____WB$wombat$assign$function_____("frames");\n"""
                """let opener = _____WB$wombat$assign$function_____("opener");\n"""
                "let arguments;\n\n"
                """document.title="HELLO";\n"""
                "}</script>"
            ),
        ),
        ContentForTests(
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"'
            ' integrity="sha512-3gJwYpMe3QewGELv8k/BX9vcqhryRdzRMxVfq6ngyWXwo03GFEzjsUm'
            '8Q7RZcHPHksttq7/GFoxjCVUjkjvPdw=="'
            ' crossorigin="anonymous" referrerpolicy="no-referrer"></script>',
            '<script src="../cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"'
            ' crossorigin="anonymous" referrerpolicy="no-referrer"></script>',
        ),
        ContentForTests(
            '<link rel="preload" src="https://cdnjs.cloudflare.com/jquery.min.js"'
            ' integrity="sha512-3gJwYpMe3QewGELv8k/BX9vcqhryRdzRMxVfq6ngyWXwo03GFEzjsUm'
            '8Q7RZcHPHksttq7/GFoxjCVUjkjvPdw=="></link>',
            '<link rel="preload" src="../cdnjs.cloudflare.com/jquery.min.js"></link>',
        ),
    ]
)
def js_rewrites(request):
    yield request.param


def test_js_rewrites(js_rewrites, no_js_notify):
    transformed = (
        HtmlRewriter(
            ArticleUrlRewriter(HttpUrl(f"http://{js_rewrites.article_url}"), set()),
            "",
            "",
            no_js_notify,
        )
        .rewrite(js_rewrites.input_str)
        .content
    )
    assert transformed == js_rewrites.expected_str


def long_path_replace_test_content(input_: str, rewriten_url: str, article_url: str):
    expected = input_.replace("http://exemple.com/a/long/path", rewriten_url)
    return ContentForTests(input_, expected, article_url)


lprtc = long_path_replace_test_content


@pytest.fixture(
    params=[
        # Normalized path is "exemple.com/a/long/path"
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "a/long/path",
            "exemple.com",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../exemple.com/a/long/path",
            "kiwix.org",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../exemple.com/a/long/path",
            "kiwix.org/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "a/long/path",
            "exemple.com/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "a/long/path",
            "exemple.com/a",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "long/path",
            "exemple.com/a/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "long/path",
            "exemple.com/a/long",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "path",
            "exemple.com/a/long/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "path",
            "exemple.com/a/long/path",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            ".",
            "exemple.com/a/long/path/yes",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../../long/path",
            "exemple.com/a/very/long/path",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../../exemple.com/a/long/path",
            "kiwix.org/another/path",
        ),
    ]
)
def rewrite_url(request):
    yield request.param


def test_rewrite(rewrite_url, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{rewrite_url.article_url}"),
                {ZimPath("exemple.com/a/long/path")},
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(rewrite_url.input_str)
        .content
        == rewrite_url.expected_str
    )


def test_extract_title(no_js_notify):
    content = """<html>
      <head>
        <title>Page title</title>
      </head>
      <body>
        <title>Wrong page title</title>
      </body>
    </html>"""

    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl("http://example.com"),
                {ZimPath("exemple.com/a/long/path")},
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(content)
        .title
        == "Page title"
    )


def test_rewrite_attributes(no_js_notify):
    rewriter = HtmlRewriter(
        ArticleUrlRewriter(HttpUrl("http://kiwix.org/"), {ZimPath("kiwix.org/foo")}),
        "",
        "",
        no_js_notify,
    )

    assert (
        rewriter.rewrite("<a href='https://kiwix.org/foo'>A link</a>").content
        == '<a href="foo">A link</a>'
    )

    assert (
        rewriter.rewrite("<img src='https://kiwix.org/foo'></img>").content
        == '<img src="foo"></img>'
    )

    assert (
        rewriter.rewrite(
            "<img srcset='https://kiwix.org/img-480w.jpg 480w, "
            "https://kiwix.org/img-800w.jpg 800w'></img>"
        ).content
        == '<img srcset="img-480w.jpg 480w, img-800w.jpg 800w"></img>'
    )


def test_rewrite_css(no_js_notify):
    output = (
        HtmlRewriter(
            ArticleUrlRewriter(HttpUrl("http://kiwix.org/"), set()),
            "",
            "",
            no_js_notify,
        )
        .rewrite(
            "<style>p { /* A comment with a http://link.org/ */ "
            "background: url('some/image.png') ; }</style>",
        )
        .content
    )
    assert (
        output == "<style>p { /* A comment with a http://link.org/ */ "
        'background: url("some/image.png") ; }</style>'
    )


def test_head_insert(no_js_notify):
    content = """<html>
    <head>
        <title>A test content</title>
    </head>
    <body></body>
    </html>"""

    content = dedent(content)

    url_rewriter = ArticleUrlRewriter(HttpUrl("http://kiwix.org/"), set())
    assert (
        HtmlRewriter(url_rewriter, "", "", no_js_notify).rewrite(content).content
        == content
    )

    assert HtmlRewriter(url_rewriter, "PRE_HEAD_INSERT", "", no_js_notify).rewrite(
        content
    ).content == content.replace("<head>", "<head>PRE_HEAD_INSERT")
    assert HtmlRewriter(url_rewriter, "", "POST_HEAD_INSERT", no_js_notify).rewrite(
        content
    ).content == content.replace("</head>", "POST_HEAD_INSERT</head>")
    assert HtmlRewriter(
        url_rewriter, "PRE_HEAD_INSERT", "POST_HEAD_INSERT", no_js_notify
    ).rewrite(content).content == content.replace(
        "<head>", "<head>PRE_HEAD_INSERT"
    ).replace(
        "</head>", "POST_HEAD_INSERT</head>"
    )


@pytest.mark.parametrize(
    "js_src,expected_js_module_path",
    [
        ("my-module-script.js", "kiwix.org/my_folder/my-module-script.js"),
        ("./my-module-script.js", "kiwix.org/my_folder/my-module-script.js"),
        ("../my-module-script.js", "kiwix.org/my-module-script.js"),
        ("../../../my-module-script.js", "kiwix.org/my-module-script.js"),
        ("/my-module-script.js", "kiwix.org/my-module-script.js"),
        ("//myserver.com/my-module-script.js", "myserver.com/my-module-script.js"),
        (
            "https://myserver.com/my-module-script.js",
            "myserver.com/my-module-script.js",
        ),
    ],
)
def test_js_module_detected_script(js_src, expected_js_module_path):

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    HtmlRewriter(
        url_rewriter=ArticleUrlRewriter(
            HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
        ),
        pre_head_insert="",
        post_head_insert="",
        notify_js_module=custom_notify,
    ).rewrite(f'<script type="module" src="{js_src}"></script>')

    assert len(js_modules) == 1
    assert js_modules[0].value == expected_js_module_path


@pytest.mark.parametrize(
    "js_src,expected_js_module_path",
    [
        ("my-module-script.js", "kiwix.org/my_folder/my-module-script.js"),
        ("./my-module-script.js", "kiwix.org/my_folder/my-module-script.js"),
        ("../my-module-script.js", "kiwix.org/my-module-script.js"),
        ("../../../my-module-script.js", "kiwix.org/my-module-script.js"),
        ("/my-module-script.js", "kiwix.org/my-module-script.js"),
        ("//myserver.com/my-module-script.js", "myserver.com/my-module-script.js"),
        (
            "https://myserver.com/my-module-script.js",
            "myserver.com/my-module-script.js",
        ),
    ],
)
def test_js_module_detected_module_preload(js_src, expected_js_module_path):

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    HtmlRewriter(
        url_rewriter=ArticleUrlRewriter(
            HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
        ),
        pre_head_insert="",
        post_head_insert="",
        notify_js_module=custom_notify,
    ).rewrite(f'<link rel="modulepreload" src="{js_src}"></script>')

    assert len(js_modules) == 1
    assert js_modules[0].value == expected_js_module_path


@pytest.mark.parametrize(
    "script_src",
    [
        ('<script src="whatever.js"></script>'),
        ('<script>console.log("HELLO")</script>'),
        ('<script type="json" src="whatever.json"></script>'),
    ],
)
def test_no_js_module_detected(script_src):

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    HtmlRewriter(
        url_rewriter=ArticleUrlRewriter(
            HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
        ),
        pre_head_insert="",
        post_head_insert="",
        notify_js_module=custom_notify,
    ).rewrite(script_src)

    assert len(js_modules) == 0


def test_js_module_base_href_src():

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    HtmlRewriter(
        url_rewriter=ArticleUrlRewriter(
            HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
        ),
        pre_head_insert="",
        post_head_insert="",
        notify_js_module=custom_notify,
    ).rewrite(
        """<head>
                <base href="../my_other_folder/">
                <script type="module" src="my-module-script.js"></script>"""
    )

    assert len(js_modules) == 1
    assert js_modules[0].value == "kiwix.org/my_other_folder/my-module-script.js"


def test_js_module_base_href_inline():

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    HtmlRewriter(
        url_rewriter=ArticleUrlRewriter(
            HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
        ),
        pre_head_insert="",
        post_head_insert="",
        notify_js_module=custom_notify,
    ).rewrite(
        """<head><base href="../my_other_folder/">
            <script type="module">
                import * from "./my-module-script.js";
            </script>
        """
    )

    assert len(js_modules) == 1
    assert js_modules[0].value == "kiwix.org/my_other_folder/my-module-script.js"


@pytest.mark.parametrize(
    "html_content, expected_base_href",
    [
        pytest.param("", None, id="empty_content"),
        pytest.param("<html></html>", None, id="empty_html"),
        pytest.param(
            "<html><head><title>Foo</title></head></html>", None, id="no_base"
        ),
        pytest.param(
            '<html><head><base href="../.."></head></html>', "../..", id="standard_case"
        ),
        pytest.param(
            '<html><head><base href="../..">', "../..", id="malformed_head"
        ),  # malformed HTML is OK
        pytest.param(
            '<html><base href="../..">', "../..", id="very_malformed_head"
        ),  # even very malformed HTML is OK
        pytest.param(
            '<base href="../..">', "../..", id="base_at_root"
        ),  # even very malformed HTML is OK
        pytest.param(
            '<html><body><base href="../.."></body></html>', None, id="base_in_body"
        ),  # but base in body is ignored
        pytest.param(
            '<html><head><base target="_blank" href="../.."></head></html>',
            "../..",
            id="base_with_target_before",
        ),
        pytest.param(
            '<html><head><base href="../.." target="_blank" ></head></html>',
            "../..",
            id="base_with_target_after",
        ),
        pytest.param(
            '<html><head><base href="../.." href=".."></head></html>',
            "../..",
            id="base_with_two_href",
        ),
        pytest.param(
            '<html><head><base href="../.."><base href=".."></head></html>',
            "../..",
            id="two_bases_with_href",
        ),
        pytest.param(
            '<html><head><base target="_blank"><base href="../.."></head></html>',
            "../..",
            id="href_in_second_base",
        ),
        pytest.param(
            '<html><head><base target="_blank"><base href="../.."><base href="..">'
            "</head></html>",
            "../..",
            id="href_in_second_base_second_href_ignored",
        ),
    ],
)
def test_extract_base_href(html_content, expected_base_href):
    assert extract_base_href(html_content) == expected_base_href


@pytest.fixture(
    params=[
        ContentForTests(
            '<html><head><base href="./"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head></head><body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base href="../"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head></head><body><a href="../foo.html"></a></body></html>',
            "kiwix.org/a/index.html",
        ),
        ContentForTests(
            '<html><head><base href="./" target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head><base target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base href="./"><base target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head><base target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base href="./"><base href="../" target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head><base target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base target="_blank"><base href="./"></head>'
            '<body><a href="foo.html"></a></body></html>',
            '<html><head><base target="_blank"></head>'
            '<body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base href="./"><base target="_blank"><base target="_foo">'
            "</head>"
            '<body><a href="foo.html"></a></body></html>',
            '<html><head><base target="_blank"><base target="_foo"></head>'
            '<body><a href="foo.html"></a></body></html>',
        ),
        ContentForTests(
            '<html><head><base href="../"></head>'
            '<body><script src="foo.js"></script></body></html>',
            '<html><head></head><body><script src="../foo.js"></script></body></html>',
            "kiwix.org/a/index.html",
        ),
        ContentForTests(
            '<html><head><base href="../"></head>'
            '<body><style>background: url("foo.css");}</style></body></html>',
            '<html><head></head><body><style>background: url("../foo.css");}</style>'
            "</body></html>",
            "kiwix.org/a/index.html",
        ),
        ContentForTests(
            '<html><head> <link rel="shortcut icon" href="favicon.ico">'
            '<base href="../"></head><body></body></html>',
            '<html><head> <link rel="shortcut icon" href="../favicon.ico">'
            "</head><body></body></html>",
            "kiwix.org/a/index.html",
        ),
    ]
)
def rewrite_base_href_content(request):
    yield request.param


def test_rewrite_base_href(rewrite_base_href_content, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{rewrite_base_href_content.article_url}"),
                {
                    ZimPath("kiwix.org/foo.html"),
                    ZimPath("kiwix.org/foo.js"),
                    ZimPath("kiwix.org/foo.css"),
                    ZimPath("kiwix.org/foo.png"),
                    ZimPath("kiwix.org/favicon.png"),
                },
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(rewrite_base_href_content.input_str)
        .content
        == rewrite_base_href_content.expected_str
    )


@pytest.mark.parametrize(
    "input_content,expected_output",
    [
        pytest.param(
            """<a type="whatever"></a>""",
            """<a type="whatever"></a>""",
            id="double_quoted_attr",
        ),
        pytest.param(
            "<a type='whatever'></a>",
            """<a type="whatever"></a>""",
            id="single_quoted_attr",
        ),
        pytest.param(
            """<a type="wha&QUOT;tever"></a>""",
            """<a type="wha&quot;tever"></a>""",
            id="uppercase_named_reference_in_attr",
        ),
        pytest.param(
            """<a type="wha&#x22;tever"></a>""",
            """<a type="wha&quot;tever"></a>""",
            id="numeric_reference_in_attr",
        ),
        pytest.param(
            """<a type="wha&#198;tever"></a>""",
            """<a type="whaÆtever"></a>""",
            id="numeric_reference_in_attr",
        ),
        pytest.param(
            """<img src="image.png?param1=value1&param2=value2">""",
            """<img src="image.png%3Fparam1%3Dvalue1%C2%B6m2%3Dvalue2">""",
            id="badly_escaped_src",
        ),
    ],
)
def test_simple_rewrite(input_content, expected_output, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(HttpUrl("http://example.com"), set()),
            "",
            "",
            no_js_notify,
        )
        .rewrite(input_content)
        .content
        == expected_output
    )


@pytest.fixture(
    params=[
        ContentForTests(
            """<img onclick="">""",
        ),
        ContentForTests(
            """<img on-whatever="foo">""",
        ),
        ContentForTests(
            """<img on="foo">""",
        ),
        ContentForTests(
            """<img to="foo">""",
        ),
        ContentForTests(
            """<img onclick="document.location.href='./index.html';">""",
            (
                """<img onclick="var _____WB$wombat$assign$function_____ = """
                "function(name) {return (self._wb_wombat &amp;&amp; "
                "self._wb_wombat.local_init &amp;&amp; "
                "self._wb_wombat.local_init(name)) || self[name]; };\n"
                "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) "
                "{ this.__WB_source = obj; return this; } }\n"
                "{\n"
                "let window = _____WB$wombat$assign$function_____(&quot;window&quot;);"
                "\n"
                "let globalThis = _____WB$wombat$assign$function_____"
                "(&quot;globalThis&quot;);\n"
                "let self = _____WB$wombat$assign$function_____(&quot;self&quot;);\n"
                "let document = "
                "_____WB$wombat$assign$function_____(&quot;document&quot;);\n"
                "let location = "
                "_____WB$wombat$assign$function_____(&quot;location&quot;);\n"
                "let top = _____WB$wombat$assign$function_____(&quot;top&quot;);\n"
                "let parent = "
                "_____WB$wombat$assign$function_____(&quot;parent&quot;);\n"
                "let frames = "
                "_____WB$wombat$assign$function_____(&quot;frames&quot;);\n"
                "let opener = "
                "_____WB$wombat$assign$function_____(&quot;opener&quot;);\n"
                "let arguments;\n\n"
                "document.location.href=&#x27;./index.html&#x27;;\n"
                """}">"""
            ),  # NOTA: quotes and ampersand are escaped since we are inside HTML attr
        ),
    ]
)
def rewrite_onxxx_content(request):
    yield request.param


def test_rewrite_onxxx_event(rewrite_onxxx_content, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{rewrite_onxxx_content.article_url}"),
                {
                    ZimPath("kiwix.org/foo.html"),
                    ZimPath("kiwix.org/foo.js"),
                    ZimPath("kiwix.org/foo.css"),
                    ZimPath("kiwix.org/foo.png"),
                    ZimPath("kiwix.org/favicon.png"),
                },
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(rewrite_onxxx_content.input_str)
        .content
        == rewrite_onxxx_content.expected_str
    )


@pytest.fixture(
    params=[
        ContentForTests(
            '<html><head><meta charset="UTF-8"></head><body>whatever</body></html>',
        ),
        ContentForTests(
            '<html><head><meta charset="ISO-8859-1"></head>'
            "<body>whatever</body></html>",
            '<html><head><meta charset="UTF-8"></head><body>whatever</body></html>',
        ),
        ContentForTests(
            "<html><head>"
            '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
            "</head><body>whatever</body></html>",
        ),
        ContentForTests(
            "<html><head>"
            '<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1">'
            "</head><body>whatever</body></html>",
            "<html><head>"
            '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
            "</head><body>whatever</body></html>",
        ),
        ContentForTests(
            '<html><head><bla charset="ISO-8859-1"></head><body>whatever</body></html>',
        ),  # do not rewrite other tags mentionning a charset
        ContentForTests(
            "<html><head>"
            '<meta http-equiv="Foo" content="text/html; charset=ISO-8859-1">'
            "</head><body>whatever</body></html>",
        ),  # do not rewrite other http-equiv mentionning a charset
    ]
)
def rewrite_meta_charset_content(request):
    yield request.param


def test_rewrite_meta_charset(rewrite_meta_charset_content, no_js_notify):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{rewrite_meta_charset_content.article_url}"),
                set(),
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(rewrite_meta_charset_content.input_str)
        .content
        == rewrite_meta_charset_content.expected_str
    )


@pytest.fixture(
    params=[
        ContentForTests(
            '<html><head><meta http-equiv="refresh" '
            'content="3;url=https://kiwix.org/somepage" />'
            "</head><body>whatever</body></html>",
            '<html><head><meta http-equiv="refresh" '
            'content="3;url=somepage" />'
            "</head><body>whatever</body></html>",
        ),
    ]
)
def rewrite_meta_http_equiv_redirect_full_content(request):
    yield request.param


def test_rewrite_meta_http_equiv_redirect_full(
    rewrite_meta_http_equiv_redirect_full_content, no_js_notify
):
    assert (
        HtmlRewriter(
            ArticleUrlRewriter(
                HttpUrl(
                    f"http://{rewrite_meta_http_equiv_redirect_full_content.article_url}"
                ),
                {ZimPath("kiwix.org/somepage")},
            ),
            "",
            "",
            no_js_notify,
        )
        .rewrite(rewrite_meta_http_equiv_redirect_full_content.input_str)
        .content
        == rewrite_meta_http_equiv_redirect_full_content.expected_str
    )


rules = HTMLRewritingRules()


@rules.drop_attribute()
def drop_all_named_attribute(attr_name: str):
    return attr_name == "all_named"


@rules.drop_attribute()
def drop_all_tag_name_attribute(tag: str):
    return tag == "all_tag"


@rules.drop_attribute()
def drop_tag_name_attribute(tag: str, attr_name: str):
    return tag == "drop_tag" and attr_name == "drop_name"


@rules.drop_attribute()
def drop_attr_name_and_value_attribute(attr_name: str, attr_value: str | None):
    return (
        attr_name == "drop_value"
        and attr_value is not None
        and attr_value.startswith("drop")
    )


@rules.drop_attribute()
def drop_if_other_attribute(attr_name: str, attrs: AttrsList):
    return attr_name == "drop_if_other" and any(
        other_name == "other" for other_name, _ in attrs
    )


@pytest.mark.parametrize(
    "tag, attr_name, attr_value, attrs, should_drop",
    [
        pytest.param("all_tag", "foo", "bar", [], True, id="drop_by_tag_name"),
        pytest.param("other_tag", "foo", "bar", [], False, id="dont_drop_by_tag_name"),
        pytest.param("foo", "all_named", "bar", [], True, id="drop_by_attr_name"),
        pytest.param(
            "foo", "other_name", "bar", [], False, id="dont_drop_by_attr_name"
        ),
        pytest.param(
            "drop_tag", "drop_name", "bar", [], True, id="drop_by_tag_and_attr_name"
        ),
        pytest.param(
            "drop_tag", "foo", "bar", [], False, id="dont_drop_by_tag_and_attr_name"
        ),
        pytest.param("foo", "drop_value", "drop_me", [], True, id="drop_by_attr_value"),
        pytest.param(
            "foo", "drop_value", "dont_drop", [], False, id="dont_drop_by_attr_value"
        ),
        pytest.param(
            "foo", "drop_value", "dont_drop", [], False, id="dont_drop_by_attr_value"
        ),
        pytest.param(
            "foo",
            "drop_if_other",
            "bar",
            [("foo", None), ("other", "foo"), ("bar", "foo")],
            True,
            id="drop_if_other",
        ),
        pytest.param(
            "foo",
            "drop_if_other",
            "bar",
            [("foo", None), ("bar", "foo")],
            False,
            id="dont_drop_if_not_other",
        ),
    ],
)
def test_html_drop_rules(
    tag: str,
    attr_name: str,
    attr_value: str | None,
    attrs: AttrsList,
    *,
    should_drop: bool,
):
    assert (
        rules._do_drop_attribute(
            tag=tag, attr_name=attr_name, attr_value=attr_value, attrs=attrs
        )
        is should_drop
    )


def test_bad_html_drop_rules_argument_name():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* is unsupported in function"):

        @bad_rules.drop_attribute()
        def bad_signature(foo: str) -> bool:
            return foo == "bar"


def test_bad_html_drop_rules_argument_type():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* in function .* must be of type"):

        @bad_rules.drop_attribute()
        def bad_signature(attr_name: int) -> bool:
            return attr_name == "bar"


@rules.rewrite_attribute()
def rewrite_tag_value(attr_name: str) -> AttrNameAndValue | None:
    if attr_name != "aname":
        return
    return (attr_name, "foo")


@rules.rewrite_attribute()
def rewrite_tag_name(attr_name: str, attr_value: str | None) -> AttrNameAndValue | None:
    if attr_name != "bad_name":
        return
    return ("good_name", attr_value)


@rules.rewrite_attribute()
def rewrite_call_notify(
    attr_name: str,
    notify_js_module: Callable[[ZimPath], None],
) -> AttrNameAndValue | None:
    if attr_name != "call_notify":
        return
    notify_js_module(ZimPath("foo"))
    return


@rules.rewrite_attribute()
def rewrite_value_with_base_href(
    attr_name: str,
    base_href: str | None,
) -> AttrNameAndValue | None:
    if attr_name != "get_base_href":
        return
    return (attr_name, base_href)


@rules.rewrite_attribute()
def rewrite_attr2_value_with_attr1_value(
    attr_name: str,
    attrs: AttrsList,
) -> AttrNameAndValue | None:
    if attr_name != "attr2":
        return
    return (attr_name, get_attr_value_from(attrs, "attr1"))


@pytest.mark.parametrize(
    "tag, attr_name, attr_value, attrs, base_href, expected_result, should_notify",
    [
        pytest.param(
            "foo",
            "aname",
            "bar",
            [],
            "",
            ("aname", "foo"),
            False,
            id="rewrite_tag_value",
        ),
        pytest.param(
            "foo",
            "bad_name",
            "bar",
            [],
            "",
            ("good_name", "bar"),
            False,
            id="rewrite_tag_name",
        ),
        pytest.param(
            "foo",
            "call_notify",
            "bar",
            [],
            "",
            ("call_notify", "bar"),
            True,
            id="call_notify",
        ),
        pytest.param(
            "foo",
            "get_base_href",
            "bar",
            [],
            "base_href_value",
            ("get_base_href", "base_href_value"),
            False,
            id="rewrite_value_with_base_href",
        ),
        pytest.param(
            "foo",
            "attr2",
            "bar",
            [("attr1", "value1")],
            "base_href_value",
            ("attr2", "value1"),
            False,
            id="rewrite_attr2_value_with_attr1_value",
        ),
    ],
)
def test_html_attribute_rewrite_rules(
    tag: str,
    attr_name: str,
    attr_value: str | None,
    attrs: AttrsList,
    base_href: str,
    expected_result: AttrNameAndValue,
    *,
    should_notify: bool,
    simple_url_rewriter,
    js_rewriter,
    css_rewriter,
):
    notified_paths = []

    def notify(path: ZimPath):
        notified_paths.append(path)

    url_rewriter = simple_url_rewriter("http://www.example.com")
    js_rewriter = js_rewriter(
        url_rewriter=url_rewriter, base_href=base_href, notify_js_module=notify
    )
    css_rewriter = css_rewriter(url_rewriter=url_rewriter, base_href=base_href)

    assert (
        rules._do_attribute_rewrite(
            tag=tag,
            attr_name=attr_name,
            attr_value=attr_value,
            attrs=attrs,
            js_rewriter=js_rewriter,
            css_rewriter=css_rewriter,
            url_rewriter=url_rewriter,
            base_href=base_href,
            notify_js_module=notify,
        )
        == expected_result
    )
    assert (len(notified_paths) > 0) == should_notify


def test_bad_html_attribute_rewrite_rules_argument_name():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* is unsupported in function"):

        @bad_rules.rewrite_attribute()
        def bad_signature(foo: str) -> AttrNameAndValue | None:
            return (foo, "bar")


def test_bad_html_attribute_rewrite_rules_argument_type():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* in function .* must be of type"):

        @bad_rules.rewrite_attribute()
        def bad_signature(attr_name: int) -> AttrNameAndValue | None:
            return (f"{attr_name}", "bar")


@rules.rewrite_tag()
def rewrite1_tag(
    tag: str,
) -> str | None:
    if tag != "rewrite1":
        return
    return "<rewriten attr1=value1 />"


@rules.rewrite_tag()
def rewrite2_tag(
    tag: str,
    attrs: AttrsList,
    *,
    auto_close: bool,
) -> str | None:
    if tag != "rewrite2":
        return

    return (
        f"<rewriten {' '.join(format_attr(*attr) for attr in attrs)}"
        f"{'/>' if auto_close else '>'}"
    )


@pytest.mark.parametrize(
    "tag, attrs, auto_close, expected_result",
    [
        pytest.param(
            "foo",
            [],
            False,
            None,
            id="do_not_rewrite_foo_tag",
        ),
        pytest.param(
            "rewrite1",
            [("attr2", "value2")],
            False,
            "<rewriten attr1=value1 />",
            id="rewrite1_tag",
        ),
        pytest.param(
            "rewrite2",
            [("attr2", "value2")],
            False,
            '<rewriten attr2="value2">',
            id="rewrite2_tag_no_close",
        ),
        pytest.param(
            "rewrite2",
            [("attr2", "value2")],
            True,
            '<rewriten attr2="value2"/>',
            id="rewrite2_tag_auto_close",
        ),
    ],
)
def test_html_tag_rewrite_rules(
    tag: str,
    attrs: AttrsList,
    *,
    auto_close: bool,
    expected_result: str | None,
):
    assert (
        rules._do_tag_rewrite(
            tag=tag,
            attrs=attrs,
            auto_close=auto_close,
        )
        == expected_result
    )


def test_bad_html_tag_rewrite_rules_argument_name():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* is unsupported in function"):

        @bad_rules.rewrite_tag()
        def bad_signature(foo: str) -> str:
            return foo


def test_bad_html_tag_rewrite_rules_argument_type():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* in function .* must be of type"):

        @bad_rules.rewrite_tag()
        def bad_signature(attrs: int) -> str:
            return f"{attrs}"


@rules.rewrite_data()
def rewrite_data_html_rewrite_context(
    html_rewrite_context: str | None,
) -> str | None:
    if html_rewrite_context != "rewrite":
        return
    return "rewritten data"


@pytest.mark.parametrize(
    "html_rewrite_context, base_href, data, expected_result",
    [
        pytest.param(
            "foo",
            "bar",
            "something",
            None,
            id="do_not_rewrite_foo_context",
        ),
        pytest.param(
            None,
            "bar",
            "something",
            None,
            id="do_not_rewrite_none_context",
        ),
        pytest.param(
            "rewrite",
            "bar",
            "something",
            "rewritten data",
            id="rewrite_data_html_rewrite_context",
        ),
    ],
)
def test_html_data_rewrite_rules(
    html_rewrite_context: str | None,
    base_href: str,
    data: str,
    *,
    expected_result: str | None,
    simple_url_rewriter,
    js_rewriter,
    css_rewriter,
):
    notified_paths = []

    def notify(path: ZimPath):
        notified_paths.append(path)

    url_rewriter = simple_url_rewriter("http://www.example.com")
    js_rewriter = js_rewriter(
        url_rewriter=url_rewriter, base_href=base_href, notify_js_module=notify
    )
    css_rewriter = css_rewriter(url_rewriter=url_rewriter, base_href=base_href)

    assert (
        rules._do_data_rewrite(
            html_rewrite_context=html_rewrite_context,
            data=data,
            css_rewriter=css_rewriter,
            js_rewriter=js_rewriter,
            url_rewriter=url_rewriter,
        )
        == expected_result
    )


def test_bad_html_data_rewrite_rules_argument_name():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* is unsupported in function"):

        @bad_rules.rewrite_data()
        def bad_signature(foo: str) -> str | None:
            return foo


def test_bad_html_data_rewrite_rules_argument_type():
    bad_rules = HTMLRewritingRules()

    with pytest.raises(TypeError, match="Parameter .* in function .* must be of type"):

        @bad_rules.rewrite_data()
        def bad_signature(data: int) -> str | None:
            return f"{data}"


@pytest.mark.parametrize(
    "tag, attr_name, attr_value, attrs, expected_result",
    [
        pytest.param(
            "meta",
            "content",
            "1;url=http://www.example.com/somewhere",
            [("http-equiv", "refresh")],
            ("content", "1;url=http://www.example.com/somewhererewritten"),
            id="nomimal_case",
        ),
        pytest.param(
            "meta",
            "content",
            "   1  ;  url =  http://www.example.com/somewhere   ",
            [("http-equiv", "refresh")],
            ("content", "1;url=http://www.example.com/somewhererewritten"),
            id="nomimal_case_with_spaces",
        ),
        pytest.param(
            "foo",
            "content",
            "1;url=http://www.example.com/somewhere",
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_foo_tag",
        ),
        pytest.param(
            "meta",
            "foo",
            "1;url=http://www.example.com/somewhere",
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_foo_attribute",
        ),
        pytest.param(
            "meta",
            "content",
            "1;url=http://www.example.com/somewhere",
            [("http-equiv", "foo")],
            None,
            id="do_not_rewrite_http_equiv_not_refresh",
        ),
        pytest.param(
            "meta",
            "content",
            "1;url=http://www.example.com/somewhere",
            [],
            None,
            id="do_not_rewrite_no_http_equiv",
        ),
        pytest.param(
            "meta",
            "content",
            None,
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_missing_attribute",
        ),
        pytest.param(
            "meta",
            "content",
            "",
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_empty_attribute",
        ),
        pytest.param(
            "meta",
            "content",
            "1",
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_attribute_without_url",
        ),
        pytest.param(
            "meta",
            "content",
            "1;foo=http://www.example.com/somewhere",
            [("http-equiv", "refresh")],
            None,
            id="do_not_rewrite_bad_attribute",
        ),
    ],
)
def test_rewrite_meta_http_equiv_redirect_rule(
    tag: str,
    attr_name: str,
    attr_value: str | None,
    attrs: AttrsList,
    expected_result: AttrNameAndValue | None,
    simple_url_rewriter,
):
    url_rewriter = simple_url_rewriter("http://www.example.com", suffix="rewritten")

    assert (
        rewrite_meta_http_equiv_redirect(
            tag=tag,
            attr_name=attr_name,
            attr_value=attr_value,
            attrs=attrs,
            url_rewriter=url_rewriter,
            base_href=None,
        )
        == expected_result
    )
