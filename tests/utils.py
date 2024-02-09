from dataclasses import dataclass


@dataclass
class ContentForTests:
    input_: str | bytes
    expected: str | bytes = ""
    article_url: str = "kiwix.org"

    def __post_init__(self):
        if not self.expected:
            self.expected = self.input_

    @property
    def input_str(self) -> str:
        if isinstance(self.input_, str):
            return self.input_
        raise ValueError("Input value is not a str.")

    @property
    def input_bytes(self) -> bytes:
        if isinstance(self.input_, bytes):
            return self.input_
        raise ValueError("Input value is not a bytes.")

    @property
    def expected_str(self) -> str:
        if isinstance(self.expected, str):
            return self.expected
        raise ValueError("Expected value is not a str.")

    @property
    def expected_bytes(self) -> bytes:
        if isinstance(self.expected, bytes):
            return self.expected
        raise ValueError("Expected value is not a bytes.")
