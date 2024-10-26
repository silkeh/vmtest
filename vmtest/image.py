import logging
import os.path
import re
import subprocess

import pyocr.tesseract as tesseract
from PIL import Image

from vmtest.i18n import tesseract_lang


def ocr_screenshot(file: str, scale: float) -> str:
    """
    OCR a screenshot file.

    :param file: Screenshot to OCR.
    :param scale: Factor with which to scale up the image for improved OCR.
    :return: Text in the file.
    """
    return str(
        tesseract.image_to_string(scaled_image(file, scale), lang=tesseract_lang())
    )


def scaled_image(file: str, scale: float) -> Image:
    """
    Scale up an image by a certain factor.

    :param file: File to scale.
    :param scale: Factor with which to scale up the image.
    :return: Scaled image.
    """
    img = Image.open(file)
    width, height = img.size

    return img.resize((int(scale * width), int(scale * height)))


def search_screenshot(file: str, text: str, match_case: bool, ocr_scale: float) -> bool:
    """
    Search a screenshot for the given text.

    :param file: Screenshot file to search in.
    :param text: Text to find.
    :param match_case: Perform a case-sensitive match.
    :param ocr_scale: Factor with which to scale up the image for improved OCR.
    :return: Boolean indicating if the text has been found or not.
    """
    data = ocr_screenshot(file, ocr_scale)
    logging.debug(f"OCR data: {repr(data)}")

    if match_case:
        return text in data

    return text.casefold() in data.casefold()


def search_screenshot_regex(
    file: str, regex: str, match_case: bool, ocr_scale: float
) -> bool:
    """
    Search a screenshot for the given regular expression.

    :param file: Screenshot file to search in.
    :param regex: Regular expression to match.
    :param match_case: Perform a case-sensitive match.
    :param ocr_scale: Factor with which to scale up the image for improved OCR.
    :return: Boolean indicating if the regular expression has been matched or not.
    """
    data = ocr_screenshot(file, ocr_scale)
    flags = re.IGNORECASE if match_case else 0

    return re.search(regex, data, flags) is not None


def make_png(file: str) -> str:
    """
    Convert the given file to a PNG.

    :param file: File to convert.
    :return: Path of the converted file.
    """
    base, _ = os.path.splitext(file)
    dest = base + ".png"

    Image.open(file).save(dest)
    os.remove(file)

    return dest


def make_timelapse(src: str, dest: str) -> None:
    """
    Create a timelapse of all screenshots in the given directory.

    :param src: Screenshot directory.
    :param dest: Timelapse output file.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            "1/3",
            "-pattern_type",
            "glob",
            "-i",
            os.path.join(src, "screenshot_*.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            dest,
        ]
    )
