import pytest

from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath

from .utils import ContentForTests


@pytest.fixture
def simple_js_rewriter(simple_url_rewriter, no_js_notify) -> JsRewriter:
    return JsRewriter(
        url_rewriter=simple_url_rewriter("http://www.example.com"),
        base_href=None,
        notify_js_module=no_js_notify,
    )


@pytest.fixture(
    params=[
        "a = this;",
        "return this.location",
        'func(Function("return this"));',
        "'a||this||that",
        "(a,b,Q.contains(i[t], this))",
        "a = this.location.href; exports.Foo = Foo; /* export className */",
    ]
)
def rewrite_this_js_content(request):
    content = request.param
    yield ContentForTests(
        content,
        content.replace("this", "_____WB$wombat$check$this$function_____(this)"),
    )


def test_this_js_rewrite(simple_js_rewriter: JsRewriter, rewrite_this_js_content):
    assert (
        simple_js_rewriter.rewrite(rewrite_this_js_content.input_str)
        == rewrite_this_js_content.expected_str
    )


class WrappedTestContent(ContentForTests):
    @staticmethod
    def wrap_script(text: str) -> str:
        """
        A small wrapper to help generate the expected content.

        JsRewriter must add this local definition around all js code (when we access on
        of the local varibles)
        """
        return (
            "var _____WB$wombat$assign$function_____ = function(name) {return (self."
            "_wb_wombat && self._wb_wombat.local_init && self._wb_wombat.local_init"
            "(name)) || self[name]; };\n"
            "if (!self.__WB_pmw) { self.__WB_pmw = function(obj) { this.__WB_source ="
            " obj; return this; } }\n"
            "{\n"
            'let window = _____WB$wombat$assign$function_____("window");\n'
            'let globalThis = _____WB$wombat$assign$function_____("globalThis");\n'
            'let self = _____WB$wombat$assign$function_____("self");\n'
            'let document = _____WB$wombat$assign$function_____("document");\n'
            'let location = _____WB$wombat$assign$function_____("location");\n'
            'let top = _____WB$wombat$assign$function_____("top");\n'
            'let parent = _____WB$wombat$assign$function_____("parent");\n'
            'let frames = _____WB$wombat$assign$function_____("frames");\n'
            'let opener = _____WB$wombat$assign$function_____("opener");\n'
            "let arguments;\n"
            "\n"
            f"{text}"
            "\n"
            "}"
        )

    def __post_init__(self):
        super().__post_init__()
        self.expected = self.wrap_script(self.expected_str)


@pytest.fixture(
    params=[
        WrappedTestContent(
            "location = http://example.com/",
            "location = ((self.__WB_check_loc && self.__WB_check_loc(location, argument"
            "s)) || {}).href = http://example.com/",
        ),
        WrappedTestContent(
            " location = http://example.com/2",
            " location = ((self.__WB_check_loc && self.__WB_check_loc(location, argumen"
            "ts)) || {}).href = http://example.com/2",
        ),
        WrappedTestContent("func(location = 0)", "func(location = 0)"),
        WrappedTestContent(
            " location = http://example.com/2",
            " location = ((self.__WB_check_loc && self.__WB_check_loc(location, argumen"
            "ts)) || {}).href = http://example.com/2",
        ),
        WrappedTestContent("window.eval(a)", "window.eval(a)"),
        WrappedTestContent("x = window.eval; x(a);", "x = window.eval; x(a);"),
        WrappedTestContent(
            "this. location = 'http://example.com/'",
            "this. location = 'http://example.com/'",
        ),
        WrappedTestContent(
            "if (self.foo) { console.log('blah') }",
            "if (self.foo) { console.log('blah') }",
        ),
        WrappedTestContent("window.x = 5", "window.x = 5"),
    ]
)
def rewrite_wrapped_content(request):
    yield request.param


def test_wrapped_rewrite(simple_js_rewriter: JsRewriter, rewrite_wrapped_content):
    assert (
        simple_js_rewriter.rewrite(rewrite_wrapped_content.input_str)
        == rewrite_wrapped_content.expected_str
    )


class ImportTestContent(ContentForTests):
    @staticmethod
    # We want to import js stored in zim file as `_zim_static/__wb_module_decl.js` from
    # `https://exemple.com/some/path/` so path is
    # `../../../_zim_static/__wb_module_decl.js`
    def wrap_import(text: str) -> str:
        """
        A small wrapper to help us generate the expected content for modules.

        JsRewriter must add this import line at beginning of module codes (when code
        contains `import` or `export`)
        """
        return (
            "import { window, globalThis, self, document, location, top, parent, "
            'frames, opener } from "../../../_zim_static/__wb_module_decl.js";\n'
            f"{text}"
        )

    def __post_init__(self):
        super().__post_init__()
        self.article_url = "https://exemple.com/some/path/"
        self.expected = self.wrap_import(self.expected_str)


@pytest.fixture(
    params=[
        # import rewrite
        ImportTestContent(
            """import "foo";

a = this.location""",
            """import "foo";

a = _____WB$wombat$check$this$function_____(this).location""",
        ),
        # import/export module rewrite
        ImportTestContent(
            """a = this.location

export { a };
""",
            """a = _____WB$wombat$check$this$function_____(this).location

export { a };
""",
        ),
        # rewrite ESM module import
        ImportTestContent(
            'import "https://example.com/file.js"',
            'import "../../../example.com/file.js"',
        ),
        ImportTestContent(
            '''
import {A, B}
 from
 "https://example.com/file.js"''',
            '''
import {A, B}
 from
 "../../../example.com/file.js"''',
        ),
        ImportTestContent(
            """
import * from "https://example.com/file.js"
import A from "http://example.com/path/file2.js";

import {C, D} from "./abc.js";
import {X, Y} from "../parent.js";
import {E, F, G} from "/path.js";
import { Z } from "../../../path.js";

B = await import(somefile);
""",
            """
import * from "../../../example.com/file.js"
import A from "../../../example.com/path/file2.js";

import {C, D} from "./abc.js";
import {X, Y} from "../parent.js";
import {E, F, G} from "../../path.js";
import { Z } from "../../path.js";

B = await ____wb_rewrite_import__(import.meta.url, somefile);
""",
        ),
        ImportTestContent(
            'import"import.js";import{A, B, C} from"test.js";(function() => { frames[0]'
            '.href = "/abc"; })',
            'import"import.js";import{A, B, C} from"test.js";(function() => { frames[0]'
            '.href = "/abc"; })',
        ),
        ImportTestContent(
            """a = location

export{ a, $ as b};
""",
            """a = location

export{ a, $ as b};
""",
        ),
    ]
)
def rewrite_import_content(request):
    yield request.param


def test_import_rewrite(no_js_notify, rewrite_import_content):
    url_rewriter = ArticleUrlRewriter(
        HttpUrl(rewrite_import_content.article_url), set()
    )
    assert (
        JsRewriter(
            url_rewriter=url_rewriter, base_href=None, notify_js_module=no_js_notify
        ).rewrite(rewrite_import_content.input_str, opts={"isModule": True})
        == rewrite_import_content.expected_str
    )


@pytest.fixture(
    params=[
        "return this.abc",
        "return this object",
        "a = 'some, this object'",
        "{foo: bar, this: other}",
        "this.$location = http://example.com/",
        "this.  $location = http://example.com/",
        "this. _location = http://example.com/",
        "this. alocation = http://example.com/",
        "this.location = http://example.com/",
        ",eval(a)",
        "this.$eval(a)",
        "x = $eval; x(a);",
        "obj = { eval : 1 }",
        "x = obj.eval",
        "x = obj.eval(a)",
        "x = obj._eval(a)",
        "x = obj.$eval(a)",
        "if (a.self.foo) { console.log('blah') }",
        "a.window.x = 5",
        "  postMessage({'a': 'b'})",
        "simport(5);",
        "a.import(5);",
        "$import(5);",
        "async import(val) { ... }",
        """function blah() {
  const text = "text: import a from B.js";
}
""",
        """function blah() {
  const text = `
import a from "https://example.com/B.js"
`;
}

""",
        "let a = 7; var b = 5; const foo = 4;\n\n",
    ]
)
def no_rewrite_js_content(request):
    yield request.param


def test_no_rewrite(simple_js_rewriter: JsRewriter, no_rewrite_js_content):
    assert simple_js_rewriter.rewrite(no_rewrite_js_content) == no_rewrite_js_content


@pytest.mark.parametrize(
    "js_src,expected_js_module_path",
    [
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
def test_js_rewrite_nested_module_detected(js_src, expected_js_module_path):

    js_modules = []

    def custom_notify(zim_path: ZimPath):
        js_modules.append(zim_path)

    url_rewriter = ArticleUrlRewriter(
        HttpUrl("http://kiwix.org/my_folder/my_article.html"), set()
    )

    JsRewriter(
        url_rewriter=url_rewriter, base_href=None, notify_js_module=custom_notify
    ).rewrite(f'import * from "{js_src}"', opts={"isModule": True})

    assert len(js_modules) == 1
    assert js_modules[0].value == expected_js_module_path
