import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest

from warc2zim.utils import set_encoding_aliases, to_string


@dataclass
class EncodedForTest:
    content: str
    encoding: str
    encoded: bytes
    valid: bool

    def __init__(self, content: str, encoding: str):
        self.content = content
        self.encoding = encoding
        try:
            self.encoded = content.encode(encoding)
            self.valid = True
        except ValueError:
            self.valid = False


@pytest.fixture(
    params=[
        "Simple ascii content",
        "A content with non ascii chars éœo€ð",
        "Latin1 contént",
        "Latin2 conteňt",
        "这是中文文本",  # "This is a chinese text" (in chinese)
    ]
)
def content(request):
    yield request.param


@pytest.fixture(
    params=[
        "ascii",
        "utf-8",
        "utf-16",
        "utf-32",
        "latin1",
        "latin2",
        "gb2312",
        "gbk",
    ]
)
def encoding(request):
    yield request.param


@pytest.fixture
def simple_encoded_content(content, encoding):
    return EncodedForTest(content, encoding)


def test_decode_http_header(simple_encoded_content):
    if not simple_encoded_content.valid:
        # Nothing to test
        return
    assert (
        to_string(
            simple_encoded_content.encoded,
            simple_encoded_content.encoding,
            [],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == simple_encoded_content.content
    )


def test_decode_bad_http_header(simple_encoded_content):
    if not simple_encoded_content.valid:
        # Nothing to test
        return
    assert (
        to_string(
            simple_encoded_content.encoded,
            # HTTP header always pretend it has been encoded with latin1
            "latin1",
            # but we luckily have the proper "try-charset"
            [simple_encoded_content.encoding],
            1024,
            # and we've disabled the use of HTTP header
            ignore_http_header_charsets=True,
            ignore_content_header_charsets=False,
        )
        == simple_encoded_content.content
    )


@dataclass
class DeclaredHtmlEncodedForTest(EncodedForTest):
    def __init__(self, content: str, encoding: str):
        html_content = f'<html><meta charset="{encoding}"><body>{content}</body></html>'
        super().__init__(html_content, encoding)


@pytest.fixture
def declared_html_encoded_content(content, encoding):
    return DeclaredHtmlEncodedForTest(content, encoding)


def test_decode_html_header(declared_html_encoded_content):
    test_case = declared_html_encoded_content
    if not test_case.valid:
        return
    assert (
        to_string(
            test_case.encoded,
            None,
            [],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == test_case.content
    )


@dataclass
class BadlyDeclaredHtmlEncodedForTest(EncodedForTest):
    def __init__(self, content: str, encoding: str):
        # pretend to be encoded with `encoding`
        html_content = f"<html><meta charset={encoding}><body>{content}</body></html>"
        # but in fact you are encoded with ISO-8859-1
        super().__init__(html_content, "ISO-8859-1")


@pytest.fixture
def badly_declared_html_encoded_content(content, encoding):
    return BadlyDeclaredHtmlEncodedForTest(content, encoding)


def test_decode_bad_html_header(badly_declared_html_encoded_content):
    test_case = badly_declared_html_encoded_content
    if not test_case.valid:
        return
    assert (
        to_string(
            test_case.encoded,
            None,
            # Indicate proper charset to use in try-charsets
            ["ISO-8859-1"],
            1024,
            ignore_http_header_charsets=False,
            # Disable charset defined in content first bytes
            ignore_content_header_charsets=True,
        )
        == test_case.content
    )


def test_decode_str(content, encoding):
    result = to_string(
        content,
        encoding,
        [],
        1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )
    assert result == content


def test_binary_content():
    content = "Hello, 你好".encode("utf-32")
    content = bytes([0xEF, 0xBB, 0xBF]) + content
    # [0xEF, 0xBB, 0xBF] is a BOM marker for utf-8
    # It will trick chardet to be really confident it is utf-8.
    # However, this cannot be properly decoded using utf-8 ; but a value is still
    # returned, since upstream server promised this is utf-8
    assert to_string(
        content,
        "UTF-8",
        [],
        1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )


def test_single_bad_character():
    content = bytes([0xEF, 0xBB, 0xBF]) + b"prem" + bytes([0xC3]) + "ière".encode()
    # [0xEF, 0xBB, 0xBF] is a BOM marker for utf-8-sig
    # 0xC3 is a bad character (nothing in utf-8-sig at this position)
    result = to_string(
        content,
        "utf-8-sig",
        [],
        1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )
    assert result == "prem�ière"


def test_decode_charset_to_try(simple_encoded_content):
    if not simple_encoded_content.valid:
        # Nothing to test
        return
    assert (
        to_string(
            simple_encoded_content.encoded,
            None,
            [simple_encoded_content.encoding],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == simple_encoded_content.content
    )


def test_decode_weird_encoding_not_declared_not_in_try_list():
    with pytest.raises(ValueError):
        to_string(
            "Latin1 contént".encode("latin1"),
            None,
            ["UTF-8"],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )


def test_decode_weird_encoding_not_declared_in_try_list():
    content = "Latin1 contént"
    assert (
        to_string(
            content.encode("latin1"),
            None,
            ["UTF-8", "latin1"],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == content
    )


@dataclass
class CharsetsTestData:
    filename: str
    probable_charset: str | None  # probable charset to use
    known_charset: str | None  # charset we know is being used (fake file typically)
    http_charset: (
        str | None
    )  # encoding to pass as http header because file is missing details and encoding is
    # not standard
    expected_strings: list[str]


def get_testdata() -> Generator[CharsetsTestData, None, None]:
    data = json.loads(
        (Path(__file__).parent / "encodings" / "definition.json").read_bytes()
    )
    for file in data["files"]:
        yield CharsetsTestData(
            filename=file["filename"],
            probable_charset=file.get("probable_charset", None),
            known_charset=file.get("known_charset", None),
            http_charset=file.get("http_charset", None),
            expected_strings=file.get("expected_strings", []),
        )


def get_testdata_id(test_data: CharsetsTestData) -> str:
    return test_data.filename


@pytest.mark.parametrize("testdata", get_testdata(), ids=get_testdata_id)
def test_decode_files(testdata: CharsetsTestData):
    result = to_string(
        (Path(__file__).parent / "encodings" / testdata.filename).read_bytes(),
        testdata.http_charset,
        ["UTF-8", "latin1"],
        1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )
    for expected_string in testdata.expected_strings:
        assert expected_string in result


def test_decode_charset_too_far_away_without_fallback():
    content = '<html><meta charset="latin1"><body>content</body></html>'
    with pytest.raises(ValueError, match="No suitable charset"):
        to_string(
            content.encode("latin1"),
            None,
            [],
            24,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )


def test_decode_charset_too_far_away_with_fallback():
    content = '<html><meta charset="latin1"><body>content</body></html>'
    assert (
        to_string(
            content.encode("latin1"),
            None,
            ["latin1"],
            24,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == content
    )


def test_decode_charset_far_away():
    content = (
        f'<html>{"".join("-" for i in range(1024))}<meta charset="latin1">'
        "<body>content</body></html>"
    )
    assert (
        to_string(
            content.encode("latin1"),
            None,
            [],
            1200,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
        == content
    )


def test_decode_charset_too_far_away_with_alias():
    content = '<html><meta charset="foo"><body>content</body></html>'
    set_encoding_aliases({"foo": "latin1"})
    to_string(
        content.encode("latin1"),
        None,
        [],
        1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )


def test_decode_charset_too_far_away_without_proper_alias():
    content = '<html><meta charset="foo"><body>content</body></html>'
    set_encoding_aliases({"bar": "latin1"})
    with pytest.raises(LookupError, match="unknown encoding: foo"):
        to_string(
            content.encode("latin1"),
            None,
            [],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        )
