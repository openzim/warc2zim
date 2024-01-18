from dataclasses import dataclass


@dataclass
class ContentForTests:
    input_: str
    expected: str = ""
    article_url: str = "kiwix.org"

    def __post_init__(self):
        if not self.expected:
            self.expected = self.input_
