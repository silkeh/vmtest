import os.path
import time
from typing import Callable, Optional, Union

from vmtest.i18n import I18n
from vmtest.image import make_png, search_screenshot, search_screenshot_regex
from vmtest.keymap import Keymap
from vmtest.keymap import _current as current_keymap
from vmtest.vm import VM
from vmtest import _log as log


class Fail(Exception):
    """
    Fail is raised when a command fails.
    """

    def __init__(self, message: str):
        """
        Initialize a failure.

        :param message: Message to fail with.
        """
        self.message = message


class Command:
    """
    Command is the interface for executing commands.
    Any implementation is expected to extend this class and implement the `exec` function.
    """

    def exec(self, vm: VM) -> None:
        """
        Run the command.

        :param vm: VM to execute the command on.
        """
        raise NotImplementedError


class Eject(Command):
    """
    Eject the CD.
    """

    def exec(self, vm: VM) -> None:
        """
        Eject the CD.
        """
        vm.eject('ide0-cd0', force=True)


class FindText(Command):
    """
    Find a given text.
    """

    def __init__(
        self,
        text: str | I18n,
        match_case: bool = False,
        regex: bool = False,
        ocr_scale: float = 3,
    ):
        """
        Find a given text.

        :param text: Text to find.
        :param match_case: Perform a case-sensitive match.
        :param regex: Interpret the text as a regular expression.
        :param ocr_scale: Scale the image by the given factor for OCR.
        """
        self._raw_text = text
        self._screenshot = Screenshot()
        self._match_case = match_case
        self._regex = regex
        self._ocr_scale = ocr_scale

    @property
    def _text(self) -> str:
        return str(self._raw_text)

    def __str__(self) -> str:
        return f"FindText({repr(self._text)})"

    def exec(self, vm: VM) -> None:
        file = self._screenshot.create(vm)

        if self._regex:
            if search_screenshot_regex(
                file, self._text, self._match_case, self._ocr_scale
            ):
                log.info("✅", f"Found {repr(self._text)}")
                return
        else:
            if search_screenshot(file, self._text, self._match_case, self._ocr_scale):
                log.info("✅", f"Found {repr(self._text)}")
                return

        raise Fail(f"{repr(self._text)} not found")


class Keys(Command):
    """
    Enter a series of keys.
    """

    def __init__(
        self,
        *args: str,
        wait: float = 1,
        interval: float = 0,
        keymap: Optional[Keymap] = None,
    ):
        """
        Enter a series of keys.

        :param args: Keys to enter.
        :param wait: Wait for this amount of seconds after entering the keys.
        :param interval: Wait for this amount of time between entering the keys.
        :param keymap: Override the keymap to use.
        """
        self._keys = list(args)
        self._wait = wait
        self._interval = interval
        self._keymap = keymap if keymap is not None else current_keymap

    def exec(self, vm: VM) -> None:
        log.info("⌨️", " ".join([repr(k) for k in self._keys]))

        for k in self._keys:
            self._keymap.send(vm, k)
            time.sleep(self._interval)

        time.sleep(self._wait)


class Text(Keys):
    """
    Enter text.
    """

    def __init__(
        self,
        text: str,
        wait: float = 1,
        interval: float = 0,
        keymap: Optional[Keymap] = None,
    ):
        """
        Enter text.

        :param text: Text to enter.
        :param wait: Wait for this amount of seconds after entering the keys.
        :param interval: Wait for this amount of time between entering the keys.
        :param keymap: Override the keymap to use.
        """
        super().__init__(*list(text), wait=wait, interval=interval, keymap=keymap)


class PowerOff(Command):
    """
    Power off the VM.
    """

    def exec(self, vm: VM) -> None:
        log.info("🔌", "Powering off the VM")
        vm.power_off()


class Reboot(Command):
    """
    Reboot the VM.
    """

    def exec(self, vm: VM) -> None:
        log.info("🔃", "Rebooting the VM")
        vm.reset()


class Screenshot(Command):
    """
    Create a screenshot.
    """

    count = 0

    def __init__(self, name: str = "", wait_before: float = 0):
        """
        Create a screenshot.

        :param name: Name of the screenshot.
        :param wait_before: Wait before taking the screenshot.
        """
        self._name = name
        self._wait_before = wait_before

    def exec(self, vm: VM) -> None:
        path = self.next()
        log.info("📸", path)
        self._create(vm, path)

    def next(self) -> str:
        """
        Get the path for the next screenshot.

        :return: Path.
        """
        c = Screenshot.count
        Screenshot.count += 1

        path = f"screenshot_{c:04}"
        path += f"_{self._name}" if self._name else ""
        path += ".tmp"

        return path

    def create(self, vm: VM) -> str:
        """
        Create a screenshot for the given VM.

        :param vm: VM to create the screenshot for.
        :return: Path to created screenshot.
        """
        time.sleep(self._wait_before)
        return self._create(vm, self.next())

    @staticmethod
    def _create(vm: VM, name: str) -> str:
        path = vm.screenshot(name)

        time.sleep(1)
        if not os.path.exists(path):
            raise Fail("Screenshot failed")

        return make_png(path)


class Sleep(Command):
    """
    Sleep for a number of seconds.
    """

    def __init__(self, seconds: float):
        """
        Sleep for a number of seconds.

        :param seconds: Number of seconds to sleep.
        """
        self.seconds = seconds

    def exec(self, vm: VM) -> None:
        log.info("⏳", f"{self.seconds} s")
        time.sleep(self.seconds)


class Sequence(Command):
    """
    Execute a sequence of commands.
    """

    def __init__(self, *commands: Command):
        """
        Execute a sequence of commands.

        :param commands: Commands to execute.
        """
        self._commands = commands

    def exec(self, vm: VM) -> None:
        for command in self._commands:
            command.exec(vm)


class And(Sequence):
    """
    Fail unless all the given commands succeed.
    """


class If(Sequence):
    """
    Execute a sequence of commands conditionally.
    """

    def __init__(self, cond: Union[bool,Callable[[VM], bool]], *commands: Command):
        """
        Execute a sequence of commands conditionally.

        :param cond: Boolean value or function that needs to return true to execute the commands.
        :param commands: Commands to execute.
        """
        super().__init__(*commands)
        self._cond = cond

    def exec(self, vm: VM) -> None:
        if self._resolve(vm):
            super().exec(vm)

    def _resolve(self, vm: VM) -> bool:
        if isinstance(self._cond, bool):
            return self._cond
        return self._cond(vm)


class IfEdition(Sequence):
    """
    Execute a sequence of commands if the edition matches.
    """

    def __init__(self, edition: str, *commands: Command):
        """
        Execute a sequence of commands if the edition matches.

        :param edition: Edition to match.
        :param commands: Commands to execute.
        """
        super().__init__(*commands)
        self._edition = edition

    def exec(self, vm: VM) -> None:
        log.info("🔀", f"{self._edition} == {vm.info.edition}")
        if vm.info.edition is not None and vm.info.edition.lower() == self._edition:
            super().exec(vm)


class IfOS(Sequence):
    """
    Execute a sequence of commands if the OS matches.
    """

    def __init__(self, osname: str, *commands: Command):
        """
        Execute a sequence of commands if the OS matches.

        :param edition: OS to match.
        :param commands: Commands to execute.
        """
        super().__init__(*commands)
        self._os = osname

    def exec(self, vm: VM) -> None:
        log.info("🔀", f"{self._os} == {vm.info.os}")
        if vm.info.os.lower() == self._os:
            super().exec(vm)


class IfRelease(Sequence):
    """
    Execute a sequence of commands if the release matches.
    """

    def __init__(self, release: str, *commands: Command):
        """
        Execute a sequence of commands if the release matches.

        :param edition: release to match.
        :param commands: Commands to execute.
        """
        super().__init__(*commands)
        self._release = release

    def exec(self, vm: VM) -> None:
        log.info("🔀", f"{self._release} == {vm.info.release}")
        if vm.info.release.lower() == self._release:
            super().exec(vm)


class Or(Sequence):
    """
    Fail unless one of the given commands succeeds.
    """

    def exec(self, vm: VM) -> None:
        failures: list[Fail] = []

        for command in self._commands:
            try:
                command.exec(vm)
                return
            except Fail as f:
                failures.append(f)

        raise Fail(f'All commands failed: {", ".join([str(f) for f in failures])}')


class WaitFor(Command):
    """
    Wait for a command to execute successfully.
    """

    def __init__(self, command: Command, attempts: int = 10, interval: int = 5):
        """
        Wait for a command to execute successfully.

        :param command: Command to execute.
        :param attempts: Number of attempts to execute the command.
        :param interval: Interval between attempts.
        """
        self._command = command
        self._attempts = attempts
        self._interval = interval

    def exec(self, vm: VM) -> None:
        error: Optional[Fail] = None

        for attempt in range(self._attempts):
            log.info(
                "🔁",
                f"{attempt}/{self._attempts} {str(self._command)} (retry in {self._interval} s)",
            )

            try:
                self._command.exec(vm)
                return
            except Fail as f:
                log.debug("😞", f"Attempt failed: {f}")
                error = f

            time.sleep(self._interval)

        raise Fail(
            f'Give up after {self._attempts} attempts: {error.message if error else ""}'
        )
