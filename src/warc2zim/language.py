from zimscraperlib.i18n import get_language_or_none

from warc2zim.constants import logger


def parse_language(input_lang: str) -> str:
    """Transform the input language into a valid ZIM Language Metadata

    Support many ways to describe the language (all ISO 639 + English label)
    Supports a comma-separated list of languages as input.
    Deduplicates languages.
    Ignore whitespaces.
    Preserve language ordering (since it conveys meaning in ZIM metadata).
    """

    # transform input language into Language object (or None if not found)
    langs = [get_language_or_none(lang.strip()) for lang in input_lang.split(",")]

    # get unique iso_639_3 codes, removing duplicates and None values, preserving order
    langs = list(
        dict.fromkeys(
            [
                lang.iso_639_3
                for lang in langs
                if lang is not None and lang.iso_639_3 is not None
            ]
        )
    )

    if len(langs) == 0:
        logger.warning(
            f"No valid language found in `{input_lang}`, fallbacking to `eng`."
        )
        return "eng"  # Fallback value should we not have detected a lang

    return ",".join(langs)
