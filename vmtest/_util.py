from typing import Any, Optional


def list_values(values: list[Optional[Any]]) -> list[Any]:
    """
    Convert a list of optional values to only contain none-optional values.
    :param values: List of values to convert.
    :return: List of actual values.
    """
    return [v for v in values if v is not None]
