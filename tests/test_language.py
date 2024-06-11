import pytest

from warc2zim.language import parse_language


@pytest.mark.parametrize(
    "input_lang, expected_lang",
    [
        pytest.param("en", "eng", id="english_2_chars"),
        pytest.param("eng", "eng", id="english_3_chars"),
        pytest.param("English", "eng", id="english_full_1"),
        pytest.param("zh", "zho", id="chinese_2_chars"),
        pytest.param("zh-hans", "zho", id="chinese_variant"),
        pytest.param("zho", "zho", id="chinese_3_chars"),
        pytest.param("Chinese", "zho", id="chinese_full_1"),
        pytest.param("chinEse", "zho", id="chinese_full_2"),
        pytest.param("patois", "eng", id="unrecognized_bad_name"),
        pytest.param("unknown,fra,unknown", "fra", id="ignore_unknown"),
        pytest.param("eng,fra", "eng,fra", id="two_langs_1"),
        pytest.param("fra,eng", "fra,eng", id="two_langs_2"),  # order must be preserved
        pytest.param("  eng ,   fra    ", "eng,fra", id="two_langs_spaces"),
        pytest.param("eng,fra,English", "eng,fra", id="duplicates"),
        pytest.param("eng;fra", "eng", id="unrecognized_bad_separator"),
    ],
)
def test_parse_language(input_lang, expected_lang):
    assert parse_language(input_lang) == expected_lang
