from dataclasses import dataclass


@dataclass
class TestContent:
    input: str
    expected: str = ""
    article_url: str = "kiwix.org"

    def __post_init__(self):
        if not self.expected:
            self.expected = self.input
