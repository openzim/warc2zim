from dataclasses import dataclass

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
        "A content with non ascii char éœo€ð",
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
        "gb2312",
        "gbk",
    ]
)
def encoding(request):
    yield request.param


@pytest.fixture
def simple_encoded_content(content, encoding):
    return EncodedForTest(content, encoding)


def test_decode(simple_encoded_content):
    if not simple_encoded_content.valid:
        # Nothing to test
        return
    assert (
        to_string(simple_encoded_content.encoded, None)
        == simple_encoded_content.content
    )


@pytest.fixture(
    params=[
        "ascii",
        "utf-8",
        "utf-16",
        "utf-32",
        "latin1",
        "gb2312",
        "gbk",
        "wrong-encoding",
    ]
)
def declared_encoding(request):
    return request.param


# This is a set of content/encoding/decoding that we know to fail.
# For exemple, the content "Simple ascii content" encoded using ascii, can be decoded
# by utf-16. However, it doesn't mean that it decoded it correctly.
# In this case, "utf-16" decoded it as "...."
# And this combination is not only based on the tuple encoding/decoding.
# The content itself may inpact if we can decode the bytes, and so if we try heuristics
# or not. No real choice to maintain a dict of untestable configuration.
FAILING_DECODE_COMBINATION = {
    # Encodings/decodings failing for simple ascii content
    "Simple ascii content": {
        # Decoding failing for simple ascii content encoded in ascii
        "ascii": ["utf-16"],
        # Decoding failing for simple ascii content encoded in utf-8
        "utf-8": [
            "utf-16",
            "utf-32",
            "gb2312",
            "gbk",
        ],
        "utf-16": ["latin1"],
        "utf-32": ["utf-16", "latin1"],
        "latin1": ["utf-16"],
        "gb2312": ["utf-16"],
        "gbk": ["utf-16"],
    },
    "A content with non ascii char éœo€ð": {
        "ascii": [],
        "utf-8": ["utf-16", "latin1"],
        "utf-16": ["latin1"],
        "utf-32": ["utf-16", "latin1"],
        "latin1": [],
        "gb2312": [],
        "gbk": [],
    },
    "这是中文文本": {
        "ascii": [],
        "utf-8": ["utf-16", "latin1"],
        "utf-16": ["latin1"],
        "utf-32": ["utf-16", "latin1"],
        "latin1": [],
        "gb2312": ["utf-16", "latin1"],
        "gbk": ["utf-16", "latin1"],
    },
}


@dataclass
class DeclaredEncodedForTest(EncodedForTest):
    declared_encoding: str
    correct: bool

    def __init__(self, content: str, encoding: str, declared_encoding: str):
        super().__init__(content, encoding)
        self.declared_encoding = declared_encoding
        self.correct = self.valid
        if (
            self.valid
            and content in FAILING_DECODE_COMBINATION
            and declared_encoding in FAILING_DECODE_COMBINATION[content][encoding]
        ):
            self.correct = False


@pytest.fixture
def declared_encoded_content(content, encoding, declared_encoding):
    return DeclaredEncodedForTest(content, encoding, declared_encoding)


def test_declared_decode(declared_encoded_content):
    test_case = declared_encoded_content
    if not test_case.valid:
        return

    decoded = to_string(test_case.encoded, test_case.declared_encoding)
    if test_case.correct:
        assert decoded == test_case.content


# This is a set of content/encoding/decoding that we know to fail.
# For exemple, the content "Simple ascii content" encoded using ascii, can be decoded
# by utf-16. However, it doesn't mean that it decoded it correctly.
# In this case, "utf-16" decoded it as "...."
# And this combination is not only based on the tuple encoding/decoding.
# The content itself may inpact if we can decode the bytes, and so if we try heuristics
# or not. No real choice to maintain a dict of untestable configuration.
FAILING_DECODE_HTML_COMBINATION = {
    # All encoding/declared_encodingcoding failing for simple ascii content
    "Simple ascii content": {
        "ascii": [],
        "utf-8": [],
        "utf-16": [],
        "utf-32": [],
        "latin1": [],
        "gb2312": [],
        "gbk": [],
    },
    "A content with non ascii char éœo€ð": {
        "ascii": [],
        "utf-8": ["latin1"],
        "utf-16": [],
        "utf-32": [],
        "latin1": [],
        "gb2312": [],
        "gbk": [],
    },
    "这是中文文本": {
        "ascii": [],
        "utf-8": ["latin1"],
        "utf-16": [],
        "utf-32": [],
        "latin1": [],
        "gb2312": ["latin1"],
        "gbk": ["latin1"],
    },
}


@dataclass
class DeclaredHtmlEncodedForTest(DeclaredEncodedForTest):
    declared_encoding: str
    correct: bool

    def __init__(self, content: str, encoding: str, declared_encoding: str):
        html_content = (
            f'<html><meta charset="{declared_encoding}"><body>{content}</body></html>'
        )

        super().__init__(html_content, encoding, declared_encoding)
        self.correct = self.valid
        if (
            self.valid
            and declared_encoding in FAILING_DECODE_HTML_COMBINATION[content][encoding]
        ):
            self.correct = False


@pytest.fixture
def declared_html_encoded_content(content, encoding, declared_encoding):
    return DeclaredHtmlEncodedForTest(content, encoding, declared_encoding)


def test_declared_decode_html(declared_html_encoded_content):
    test_case = declared_html_encoded_content
    if not test_case.valid:
        return

    html_decoded = to_string(test_case.encoded, None)
    if test_case.correct:
        assert html_decoded == test_case.content


def test_decode_str(content, declared_encoding):
    assert to_string(content, declared_encoding) == content


def test_binary_content():
    content = "Hello, 你好".encode("utf-32")
    content = bytes([0xEF, 0xBB, 0xBF]) + content
    # [0xEF, 0xBB, 0xBF] is a BOM marker for utf-8
    # It will trick chardet to be really confident it is utf-8.
    # However, this cannot be decoded using utf-8
    with pytest.raises(ValueError):
        assert to_string(content, None)

    with pytest.raises(ValueError):
        # Make coverage pass on code avoiding us to try the same encoding twice
        assert to_string(content, "UTF-8-SIG")
