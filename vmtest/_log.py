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
