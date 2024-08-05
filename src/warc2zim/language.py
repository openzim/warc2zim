from zimscraperlib.i18n import get_language_details

from warc2zim.constants import logger


def parse_language(input_lang: str) -> str:
    """Transform the input language into a valid ZIM Language Metadata

    Support many ways to describe the language (all ISO 639 + English label)
    Supports a comma-separated list of languages as input.
    Deduplicates languages.
    Ignore whitespaces.
    Preserve language ordering (since it conveys meaning in ZIM metadata).
    """

    langs = []  # use a list to preserve order

    for lang in [lang.strip() for lang in input_lang.split(",")]:
        try:
            lang_data = get_language_details(lang)
            if parsed_lang := (lang_data.iso_639_3 if lang_data else None):
                if parsed_lang not in langs:
                    langs.append(parsed_lang)
        except Exception:
            logger.warning(f"Skipping invalid language setting `{lang}`.")
            continue  # skip unrecognized

    if len(langs) == 0:
        logger.warning(
            f"No valid language found in `{input_lang}`, fallbacking to `eng`."
        )
        return "eng"  # Fallback value should we not have detected a lang

    return ",".join(langs)
