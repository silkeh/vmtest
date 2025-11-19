#!/usr/bin/env python3
import os

from vmtest.command import (
    And,
    Eject,
    FindText,
    If,
    IfEdition,
    Keys,
    Or,
    Reboot,
    Screenshot,
    Sequence,
    Sleep,
    Text,
    WaitFor,
)


def find_or_zoom(text) -> Or:
    return Or(FindText(text),
              And(Keys("ctrl-shift-equal"), FindText(text)))


class MenuItem(Sequence):
    def __init__(self, text: str, also_accept: list[str] = None):
        if also_accept is None:
            also_accept = []

        self.text = text
        super().__init__(
            Keys("meta_l", wait=2),
            Text(text, wait=2),
            Or(*[FindText(t) for t in [text] + also_accept]),
            Keys("return"),
        )

    def __str__(self) -> str:
        return f"MenuItem({self.text})"


class Solus:
    def __init__(self, swap: str = "default", fs: str = "default", luks: bool = False):
        self.swap = swap
        self.fs = fs
        self.luks = luks
        self.user_fullname = "Test User"
        self.user_name = "user"
        self.user_password = "password123"
        self.firmware = os.environ.get('VM_BOOT', 'efi')

    def _partitioning(self) -> Sequence:
        commands = [
            WaitFor(FindText("Erase disk")),
            Keys("tab", "tab", "tab", "space", wait=1),
            Keys("tab"),
        ]

        match self.swap:
            case "default":
                # Not picked up by OCR :(
                # commands.append(WaitFor(FindText('no swap')))
                pass
            case "no_hibernate":
                commands.append(Keys("down"))
                commands.append(WaitFor(FindText("no hibernate")))
            case "hibernate":
                commands.append(Keys("down", "down", interval=1, wait=0))
                commands.append(WaitFor(FindText("with hibernate")))
            case _:
                raise ValueError(f"invalid swap mode: {self.swap}")

        commands.append(Keys("tab"))

        match self.fs:
            case "default":
                pass
            case "btrfs":
                commands.append(Keys("b"))
                WaitFor(FindText("btrfs"))
            case "ext4":
                commands.append(Keys("e"))
                WaitFor(FindText("ext4"))
            case "f2fs":
                commands.append(Keys("f"))
                WaitFor(FindText("f2fs"))
            case _:
                raise ValueError(f"invalid filesystem: {self.fs}")

        commands.append(Keys("tab"))

        if self.luks:
            commands.append(
                Sequence(
                    Keys("alt-c", "alt-c", "space", "tab"),
                    # Not detected, do it blind...
                    # WaitFor(FindText('Passphrase'))
                    Text(self.user_password + "\t"),
                    Text(self.user_password + "\t"),
                )
            )

        commands.append(Screenshot())
        return Sequence(*commands)

    def install(self) -> Sequence:
        return Sequence(
            Sleep(10),
            # Open installer
            IfEdition(
                "gnome",
                WaitFor(FindText("search")),
                Keys("meta_l", wait=1),  # Exit menu
                Sleep(20),  # Wait for network
            ),
            WaitFor(MenuItem("Install")),
            WaitFor(FindText("Solus")),
            # Wait for locale detection
            Sleep(2),
            # Change language
            Keys("tab", "tab", "tab", "tab"),
            Keys("n", "a", "a", "a", "a", interval=1),
            WaitFor(FindText("set up Solus on your computer")),
            Keys("alt-n", wait=1),
            # Region
            WaitFor(FindText("The system language will be set to")),
            Keys("alt-n", wait=1),
            # Keyboard
            WaitFor(FindText("Keyboard model")),
            Keys("alt-n", wait=1),
            # Configure partitioning
            self._partitioning(),
            Keys("alt-n", wait=1),
            # Configure user
            WaitFor(FindText("name")),
            Text(self.user_fullname + "\t"),
            Text(self.user_name + "\t"),
            Text("testvm\t"),
            Text(self.user_password + "\t"),
            Text(self.user_password + "\t"),
            Keys("space"),  # auto-login
            Screenshot(),
            Keys("alt-n", wait=1),
            # Start install
            WaitFor(FindText("This is an overview")),
            Keys("alt-i", wait=1),
            # Wait for install
            WaitFor(FindText("All done"), attempts=60, interval=5),
            Keys("alt-r", wait=1),
            Screenshot(),
            Keys("alt-d", wait=1),
            Screenshot(),
            Eject(),
            Reboot(),
        )

    def boot_to_desktop(self) -> Sequence:
        return Sequence(
            If(self.luks,
               WaitFor(FindText("enter passphrase for disk")),
               Text(self.user_password + "\n"),
               ),
            Sleep(5),
            IfEdition(
                "budgie",
                WaitFor(Or(FindText("testvm"), FindText("Test User"))),
                Text(self.user_password + "\n"),
                Sleep(5),
            ),
            IfEdition(
                "xfce-beta",
                WaitFor(FindText("Test User")),
                Text(self.user_password + "\n"),
                Sleep(5),
            ),
            IfEdition(
                "gnome",
                WaitFor(Or(FindText("search"), FindText("software updates"))),
                Keys("meta_l", wait=1),  # Exit menu
            ),
        )

    def show_info_terminal(self) -> Sequence:
        return Sequence(
            WaitFor(MenuItem("terminal", also_accept=["konsole", "applications"])),
            Sleep(1),
            WaitFor(find_or_zoom("testvm")),
            # proof commands
            Text("cat /etc/vconsole.conf\n"),
            Text("cat /proc/cmdline\n"),
            WaitFor(find_or_zoom('KEYMAP')),
            Text("bootctl 2>/dev/null | head -n2\n"),
            If(self.firmware == 'efi', WaitFor(find_or_zoom("UEFI"))),
            If(self.firmware == 'legacy', WaitFor(find_or_zoom("Not booted with EFI"))),
            Text("free -h\n"),
            Text("lsblk\n"),
            Text("findmnt -t btrfs,ext4,f2fs | cat\n"),
            WaitFor(find_or_zoom("TARGET")),
            Screenshot(),
        )
