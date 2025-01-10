import logging
import os.path
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

import vmtest._log as log
from vmtest._util import list_values


def _pid_from_file(file: str) -> Optional[int]:
    if not os.path.exists(file):
        return None

    with open(file, "r") as f:
        return int(f.read())


def _pid_from_file_exists(file: str) -> bool:
    pid = _pid_from_file(file)
    if pid is None:
        return False

    return _pid_exists(pid)


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _filesize_gib(path: str) -> float:
    return os.path.getsize(path) / (1 << 30)


@dataclass
class Info:
    """
    Info contains basic information about a VM.
    """

    os: str
    release: str
    edition: Optional[str] = None
    variant: Optional[str] = None

    @property
    def vm_name(self) -> str:
        """
        Get the VM name as generated QuickEmu.
        :return: Name
        """
        return "-".join(self.__list)

    @property
    def __list(self) -> list[str]:
        if self.edition and self.variant:
            return [self.os, self.release, self.edition, self.variant]

        if self.edition:
            return [self.os, self.release, self.edition]

        return [self.os, self.release]

    def __str__(self) -> str:
        return " ".join(self.__list)


class VM:
    def __init__(
        self,
        info: Info,
        socket_path: str,
        screenshot_dir: str,
    ):
        self.info = info
        self._screenshot_dir = screenshot_dir
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(socket_path)

    def __del__(self) -> None:
        self._exec("system_powerdown")
        self._socket.close()

    def _exec(self, *args: str) -> None:
        log.debug("🖥️", f"VM command: {args}")
        self._socket.sendall((" ".join(args) + "\n").encode())

    def reset(self) -> None:
        """
        Reset the VM.
        """
        self._exec("system_reset")

    def power_off(self) -> None:
        """
        Power off the VM.
        """
        self._exec("system_powerdown")

    def screenshot(self, name: str) -> str:
        """
        Create a screenshot.

        :param name: Name of the screenshot.
        :return: Screenshot location.
        """
        name = os.path.join(self._screenshot_dir, name)
        self._exec("screendump", name)
        return name

    def send_key(self, combo: str) -> None:
        """
        Send a key (combination) to the VM.

        :param combo: Key (combination) to send.
        """
        self._exec("sendkey", combo)

    def eject(self, device: str, force: bool = False) -> None:
        """
        Eject a removable medium.

        :param device: Block device to eject.
        :param force: Eject even when in use.
        """
        if force:
            self._exec('eject', '-f', device)
        else:
            self._exec('eject', device)

    def remove(self, keep_iso: bool = False) -> None:
        """
        Remove the VM.

        :param keep_iso: Keep the ISO file.
        """
        pass


class QuickEmu(VM):
    """
    QuickEmu is a VM created via QuickEmu.
    """

    _pid: Optional[str] = None

    def __init__(
        self,
        dir: str,
        info: Info,
        width: int,
        height: int,
        screenshot_dir: str,
        reuse_vm: bool = False,
        reuse_disk: bool = False,
        create_config: bool = True,
    ):
        """
        Create a QuickEmu VM.

        :param dir: Directory to store VMs in.
        :param info: Information about the VM.
        :param width: Screen width in pixels.
        :param height: Screen height in pixels.
        :param screenshot_dir: Directory to store screenshots in.
        :param reuse_vm: Allow re-using a running VM.
        :param reuse_disk: Allow re-using an existing disk image.
        :param create_config: Create the configuration for the VM.
        """
        disk_path = os.path.join(info.vm_name, "disk.qcow2")
        socket_path = os.path.join(dir, info.vm_name, f"{info.vm_name}-monitor.socket")
        disk = os.path.join(dir, disk_path)
        self._dir = os.path.join(dir, info.vm_name)
        self._pid = os.path.join(dir, info.vm_name, f"{info.vm_name}.pid")

        os.makedirs(os.path.join(dir, info.vm_name), mode=0o0775, exist_ok=True)

        if os.path.exists(self._pid) and _pid_from_file_exists(self._pid):
            if reuse_vm:
                log.warning("⚠️", "Reusing running VM")
                super().__init__(
                    info=info, socket_path=socket_path, screenshot_dir=screenshot_dir
                )
                return
            else:
                raise ValueError("VM is already running")

        if os.path.exists(disk) and _filesize_gib(disk) >= 1:
            if reuse_disk:
                log.warning("⚠️", "Reusing existing VM disk")
            else:
                raise ValueError("VM disk already exists")

        conf, opts = self._env_options(self._vm_options(info.vm_name, width, height))
        if create_config:
            self._write_config(dir, info.vm_name, conf)

        log.info("🚀", f"Starting VM {info.vm_name} (options: {opts})")
        subprocess.run(
            ["quickemu", "--vm", f"{info.vm_name}.conf"] + opts,
            cwd=dir,
            check=True,
            stdout=self._subprocess_output(),
            stderr=self._subprocess_output(),
        )

        while not os.path.exists(socket_path):
            time.sleep(0.1)

        super().__init__(
            info=info, socket_path=socket_path, screenshot_dir=screenshot_dir
        )

    @staticmethod
    def _write_config(dir: str, name: str, conf: dict[str, str]) -> None:
        with open(os.path.join(dir, f"{name}.conf"), "w") as f:
            f.write("#!/usr/bin/quickemu --vm\n")
            for k, v in conf.items():
                f.write(f"{k}={repr(v)}\n")

    @staticmethod
    def _vm_options(name: str, width: int, height: int) -> dict[str, str]:
        return {
            "display": "spice",
            "width": str(width),
            "height": str(height),
            "firmware": "efi",
            "guest_os": "linux",
            "iso": os.path.join(name, f"{name}.iso"),
            "disk_img": os.path.join(name, "disk.qcow2"),
        }

    @staticmethod
    def _env_options(defaults: dict[str, str]) -> tuple[dict[str, str], list[str]]:
        options = defaults.copy()
        options.update(
            {
                k.removeprefix("VM_").lower(): v
                for k, v in os.environ.items()
                if k.startswith("VM_")
            }
        )

        return options, [o for o in options.pop("vm_opts", "").split(" ") if o]

    @staticmethod
    def _subprocess_output() -> Optional[int]:
        if logging.root.level <= logging.DEBUG:
            return None

        return subprocess.DEVNULL

    def __del__(self) -> None:
        self._kill()

    def _kill(self) -> None:
        if not self._pid:
            return

        pid = _pid_from_file(self._pid)
        if pid is None:
            return

        log.debug("🔨", f"killing VM PID {pid}")
        os.kill(pid, signal.SIGTERM)
        while _pid_exists(pid):
            time.sleep(1)

    def remove(self, keep_iso: bool = False) -> None:
        self._kill()

        for dir_path, _, files in os.walk(self._dir):
            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext != ".iso" or not keep_iso:
                    os.remove(os.path.join(dir_path, filename))


class QuickGet(QuickEmu):
    def __init__(
        self,
        dir: str,
        info: Info,
        width: int,
        height: int,
        screenshot_dir: str,
        reuse_vm: bool,
        reuse_disk: bool,
    ):
        """
        Create a VM using QuickGet and QuickEmu.

        :param dir: Directory to store VMs in.
        :param info: Information about the VM.
        :param width: Screen width in pixels.
        :param height: Screen height in pixels.
        :param screenshot_dir: Directory to store screenshots in.
        :param reuse_vm: Allow re-using a running VM.
        :param reuse_disk: Allow re-using an existing disk image.
        """
        log.info("⬇️", f"Retrieving VM for {info}")
        self._remove_config(dir, info.vm_name)

        subprocess.run(
            list_values(["quickget", info.os, info.release, info.edition]),
            cwd=dir,
            check=True,
            stdout=self._subprocess_output(),
            stderr=self._subprocess_output(),
        )

        conf, _ = self._env_options(self._vm_options(info.vm_name, width, height))
        self._append_config(dir, info.vm_name, conf)

        super().__init__(
            dir=dir,
            info=info,
            width=width,
            height=height,
            reuse_vm=reuse_vm,
            reuse_disk=reuse_disk,
            screenshot_dir=screenshot_dir,
            create_config=False,
        )

    @staticmethod
    def _vm_options(name: str, width: int, height: int) -> dict[str, str]:
        return {
            "display": "spice",
            "width": str(width),
            "height": str(height),
        }

    @staticmethod
    def _remove_config(dir: str, name: str) -> None:
        conf = os.path.join(dir, f"{name}.conf")
        if os.path.exists(conf):
            os.remove(conf)

    @staticmethod
    def _append_config(dir: str, name: str, conf: dict[str, str]) -> None:
        with open(os.path.join(dir, f"{name}.conf"), "a") as f:
            f.write("# Options added by vmtest\n")
            for k, v in conf.items():
                f.write(f"{k}={repr(v)}\n")
