from dataclasses import dataclass

import yaml


class I18n:
    """
    Localized string.
    """

    def __init__(self, key: str):
        """
        Initialize a localized string.

        :param key: Localization key from the configuration.
        """
        self.key = key

    def __str__(self) -> str:
        return localize(self.key)


@dataclass
class Localization:
    """
    Localization configuration.
    """

    tesseract: str
    values: dict[str, str]

    @staticmethod
    def from_file(path: str) -> "Localization":
        """
        Load the configuration from a file.

        :param path: Path to the configuration file.
        :return: Decoded config.
        """
        with open(path, "rb") as f:
            return Localization(**yaml.safe_load(f))

    def get(self, key: str) -> str:
        """
        Get the translation for a value.

        :param key: Translation key.
        :return: Translation.
        """
        return self.values[key]


_current: Localization = Localization(tesseract="eng", values={})


def load_localization(path: str) -> None:
    """
    Load translation configuration from a file and set it as currently used.

    :param path: Path to the configuration file.
    """
    global _current
    _current = Localization.from_file(path)


def tesseract_lang() -> str:
    """
    Get the current Tesseract language for OCR.

    :return: Current Tesseract langauge.
    """
    global _current
    return _current.tesseract


def localize(key: str) -> str:
    """
    Get a translation value from the currently active localization.

    :param key: Translation key.
    :return: Translation.
    """
    if _current is None:
        raise ValueError("No localization defined")

    return _current.get(key)
