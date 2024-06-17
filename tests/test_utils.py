import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest

from warc2zim.utils import to_string


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
        to_string(simple_encoded_content.encoded, simple_encoded_content.encoding, [])
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
    assert to_string(test_case.encoded, None, []) == test_case.content


def test_decode_str(content, encoding):
    result = to_string(content, encoding, [])
    assert result == content


def test_binary_content():
    content = "Hello, 你好".encode("utf-32")
    content = bytes([0xEF, 0xBB, 0xBF]) + content
    # [0xEF, 0xBB, 0xBF] is a BOM marker for utf-8
    # It will trick chardet to be really confident it is utf-8.
    # However, this cannot be properly decoded using utf-8 ; but a value is still
    # returned, since upstream server promised this is utf-8
    assert to_string(content, "UTF-8", [])


def test_single_bad_character():
    content = bytes([0xEF, 0xBB, 0xBF]) + b"prem" + bytes([0xC3]) + "ière".encode()
    # [0xEF, 0xBB, 0xBF] is a BOM marker for utf-8-sig
    # 0xC3 is a bad character (nothing in utf-8-sig at this position)
    result = to_string(content, "utf-8-sig", [])
    assert result == "prem�ière"


def test_decode_charset_to_try(simple_encoded_content):
    if not simple_encoded_content.valid:
        # Nothing to test
        return
    assert (
        to_string(
            simple_encoded_content.encoded, None, [simple_encoded_content.encoding]
        )
        == simple_encoded_content.content
    )


def test_decode_weird_encoding_not_declared_not_in_try_list():
    with pytest.raises(ValueError):
        to_string("Latin1 contént".encode("latin1"), None, ["UTF-8"])


def test_decode_weird_encoding_not_declared_in_try_list():
    content = "Latin1 contént"
    assert to_string(content.encode("latin1"), None, ["UTF-8", "latin1"]) == content


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
    )
    for expected_string in testdata.expected_strings:
        assert expected_string in result
