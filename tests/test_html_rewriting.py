from textwrap import dedent

import pytest

from warc2zim.content_rewriting.html import HtmlRewriter, extract_base_href
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
        ContentForTests("<img src />"),
        ContentForTests("<code>&lt;script&gt;</code>"),
        ContentForTests(
            "<p> This is a smiley (🙂) and it html hex value (&#x1F642;) </p>"
        ),
        ContentForTests(
            '<script type="json">{"window": "https://kiwix.org/path"}</script>'
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
        ContentForTests(
            '<script>{"window": "https://kiwix.org/path"}</script>',
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
                """{"window": "https://kiwix.org/path"}\n"""
                "}</script>"
            ),
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
        # Nota: lambda below is a trick, we should assign an ArticleUrlRewriter
        HtmlRewriter(
            lambda _: "kiwix.org",  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType]
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
