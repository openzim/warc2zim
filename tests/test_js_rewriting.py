import pytest
from warc2zim.content_rewriting import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter
from textwrap import dedent
from .utils import TestContent


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
    yield TestContent(
        content,
        content.replace("this", "_____WB$wombat$check$this$function_____(this)"),
    )


def test_this_js_rewrite(rewrite_this_js_content):
    assert (
        JsRewriter(lambda x: x).rewrite(rewrite_this_js_content.input)
        == rewrite_this_js_content.expected
    )


class WrappedTestContent(TestContent):
    @staticmethod
    def wrapScript(text: str) -> str:
        """
        A small wrapper to help generate the expected content.
        JsRewriter must add this local definition around all js code (when we access on of the local varibles)
        """
        return f"""var _____WB$wombat$assign$function_____ = function(name) {{return (self._wb_wombat && self._wb_wombat.local_init && self._wb_wombat.local_init(name)) || self[name]; }};
if (!self.__WB_pmw) {{ self.__WB_pmw = function(obj) {{ this.__WB_source = obj; return this; }} }}
{{
let window = _____WB$wombat$assign$function_____("window");
let globalThis = _____WB$wombat$assign$function_____("globalThis");
let self = _____WB$wombat$assign$function_____("self");
let document = _____WB$wombat$assign$function_____("document");
let location = _____WB$wombat$assign$function_____("location");
let top = _____WB$wombat$assign$function_____("top");
let parent = _____WB$wombat$assign$function_____("parent");
let frames = _____WB$wombat$assign$function_____("frames");
let opener = _____WB$wombat$assign$function_____("opener");
let arguments;

{text}

}}"""

    def __post_init__(self):
        super().__post_init__()
        self.expected = self.wrapScript(self.expected)


@pytest.fixture(
    params=[
        WrappedTestContent(
            "location = http://example.com/",
            "location = ((self.__WB_check_loc && self.__WB_check_loc(location, arguments)) || {}).href = http://example.com/",
        ),
        WrappedTestContent(
            " location = http://example.com/2",
            " location = ((self.__WB_check_loc && self.__WB_check_loc(location, arguments)) || {}).href = http://example.com/2",
        ),
        WrappedTestContent("func(location = 0)", "func(location = 0)"),
        WrappedTestContent(
            " location = http://example.com/2",
            " location = ((self.__WB_check_loc && self.__WB_check_loc(location, arguments)) || {}).href = http://example.com/2",
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


def test_wrapped_rewrite(rewrite_wrapped_content):
    assert (
        JsRewriter(lambda x: x).rewrite(rewrite_wrapped_content.input)
        == rewrite_wrapped_content.expected
    )


class ImportTestContent(TestContent):
    @staticmethod
    # We want to import js stored in zim file as `_zim_static/__wb_module_decl.js` from `https://exemple.com/some/path/`
    # so path is `../../../_zim_static/__wb_module_decl.js`
    def wrapImport(text: str) -> str:
        """
        A small wrapper to help us generate the expected content for modules.
        JsRewriter must add this import line at beginning of module codes (when code contains `import` or `export`)
        """
        return f"""import {{ window, globalThis, self, document, location, top, parent, frames, opener }} from "../../../_zim_static/__wb_module_decl.js";
{text}"""

    def __post_init__(self):
        super().__post_init__()
        self.article_url = "https://exemple.com/some/path/"
        self.expected = self.wrapImport(self.expected)


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

import {C, D} from "abc.js";
import {X, Y} from "../parent.js";
import {E, F, G} from "../../path.js";
import { Z } from "../../path.js";

B = await ____wb_rewrite_import__(import.meta.url, somefile);
""",
        ),
        ImportTestContent(
            'import"import.js";import{A, B, C} from"test.js";(function() => { frames[0].href = "/abc"; })',
            'import"import.js";import{A, B, C} from"test.js";(function() => { frames[0].href = "/abc"; })',
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


def test_import_rewrite(rewrite_import_content):
    url_rewriter = ArticleUrlRewriter(rewrite_import_content.article_url, set())
    assert (
        JsRewriter(url_rewriter).rewrite(rewrite_import_content.input)
        == rewrite_import_content.expected
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


def test_no_rewrite(no_rewrite_js_content):
    assert (
        JsRewriter(lambda x: x).rewrite(no_rewrite_js_content) == no_rewrite_js_content
    )
