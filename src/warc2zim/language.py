from zimscraperlib.i18n import get_language_details

from warc2zim.constants import logger


def parse_language(input_lang: str) -> str:
    """Transform the input language into a valid ZIM Language Metadata"""
    try:
        lang_data = get_language_details(input_lang)
        return lang_data["iso-639-3"]
    except Exception:
        logger.error(f"Invalid language setting `{input_lang}`. Using `eng`.")
        return "eng"
