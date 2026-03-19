from langdetect import detect, LangDetectException


def detect_language(text: str) -> str:
    """Detect the language of input text. Returns ISO 639-1 code (e.g., 'zh-cn', 'en')."""
    if not text or not text.strip():
        return "en"
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return "en"


def is_chinese(lang: str) -> bool:
    return lang.startswith("zh")


def get_search_languages(lang: str) -> list[str]:
    """Return list of languages to search in based on detected language."""
    if is_chinese(lang):
        return ["zh", "en"]
    return [lang]
