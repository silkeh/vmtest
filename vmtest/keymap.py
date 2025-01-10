from .vm import VM


class Keymap:
    """A Keymap represents a mapping of keys (as string) to QEMU sendkey commands."""

    def __init__(self, mapping: dict[str, str]):
        """
        Create a keymap from a dictionary mapping.

        Missing mappings are handled automatically by prepending `shift` for uppercase letters,
        and sending the value directly otherwise.

        :param mapping: Mapping of strings to QEMU sendkey commands.
        """
        self.__map = mapping

    def map(self, key: str) -> str:
        """
        Return the QEMU sendkey value for a given key string.

        :param key: Key string to map.
        :return: Mapped value
        """
        if key in self.__map:
            return self.__map[key]

        if key.isupper():
            return f"shift-{key.lower()}"

        return key

    def send(self, vm: VM, key: str) -> None:
        """
        Map and send the key to the given VM.

        :param vm: VM to send the key to.
        :param key: Key to send.
        """
        vm.send_key(self.map(key))


# US English keymap.
EN_US = Keymap(
    {
        "`": "grave",
        "~": "shift-grave",
        "!": "shift-1",
        "@": "shift-2",
        "#": "shift-3",
        "$": "shift-4",
        "%": "shift-5",
        "^": "shift-6",
        "&": "shift-7",
        "*": "shift-8",
        "(": "shift-9",
        ")": "shift-0",
        "-": "minus",
        "_": "shift-minus",
        "=": "equal",
        "+": "shift-equal",
        "[": "bracketleft",
        "{": "shift-bracketleft",
        "]": "bracketright",
        "}": "shift-bracketright",
        "\\": "backslash",
        "|": "shift-backslash",
        ";": "semicolon",
        ":": "shift-semicolon",
        "'": "apostrophe",
        ",": "comma",
        "<": "shift-comma",
        ">": "shift-dot",
        "/": "slash",
        "?": "shift-slash",
        ".": "dot",
        " ": "spc",
        "space": "spc",
        "enter": "ret",
        "return": "ret",
        "\n": "ret",
        "escape": "esc",
        "esc": "esc",
        "tab": "tab",
        "\t": "tab",
    }
)

# Current keymap.
_current = EN_US


def set_keymap(new: Keymap) -> None:
    """
    Update the active keymap.

    :param new: Keymap to use.
    """
    global _current
    _current = new
