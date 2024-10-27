import os
from typing import Any, Optional


def getenv_bool(key: str, default: bool = False) -> bool:
    """
    Get the value of a boolean environment value.

    :param key: Name of the environment value.
    :param default: Value if not set.
    :return: Environment variable value or default.
    """
    if key not in os.environ:
        return default

    return strtobool(os.environ[key])


def list_values(values: list[Optional[Any]]) -> list[Any]:
    """
    Convert a list of optional values to only contain none-optional values.
    :param values: List of values to convert.
    :return: List of actual values.
    """
    return [v for v in values if v is not None]


def strtobool(value: Optional[str]) -> bool:
    """
    Convert a string to a boolean.
    The string is not case-sensitive.
    False values are: 0, f, false, n, no
    True values are: 1, t, true, y, yes
    'None' (Python type) is interpreted as False.

    :param value: String to convert
    :return: Boolean value interpreted from the string.
    """
    if value is None:
        return False

    value = value.lower()
    if value in ("0", "f", "false", "n", "no"):
        return False
    if value in ("1", "t", "true", "y", "yes"):
        return True

    raise ValueError(f"Not a boolean: {repr(value)}")
