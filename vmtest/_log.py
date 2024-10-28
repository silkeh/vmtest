import logging
import os
from pathlib import Path


def setup(log_dir: str | Path) -> None:
    """
    Set up logging for the CLI applications.

    :param log_dir: Directory to store logs in.
    """
    os.makedirs(log_dir, mode=0o0775, exist_ok=True)
    logging.basicConfig(
        level=logging.getLevelName(os.environ.get("LOG_LEVEL", "info").upper()),
        format="%(message)s",
    )

    handler = logging.FileHandler(os.path.join(log_dir, "vmtest.log"))
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logging.getLogger().addHandler(handler)


def debug(icon: str, msg: str, *args: object) -> None:
    """
    Log a message with severity 'DEBUG' on the root logger.

    :param icon: Icon to include in the message.
    :param msg: Message or template string.
    :param args: Optional values for the template string.
    """
    logging.debug(icon + " " + msg, *args)


def info(icon: str, msg: str, *args: object) -> None:
    """
    Log a message with severity 'INFO' on the root logger.

    :param icon: Icon to include in the message.
    :param msg: Message or template string.
    :param args: Optional values for the template string.
    """
    logging.info(icon + " " + msg, *args)


def warning(icon: str, msg: str, *args: object) -> None:
    """
    Log a message with severity 'WARNING' on the root logger.

    :param icon: Icon to include in the message.
    :param msg: Message or template string.
    :param args: Optional values for the template string.
    """
    logging.warning(icon + " " + msg, *args)


def error(icon: str, msg: str, *args: object) -> None:
    """
    Log a message with severity 'ERROR' on the root logger.

    :param icon: Icon to include in the message.
    :param msg: Message or template string.
    :param args: Optional values for the template string.
    """
    logging.error(icon + " " + msg, *args)
