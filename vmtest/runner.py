import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from vmtest import _log as log
from vmtest._util import getenv_bool
from vmtest.command import Command, Fail, Screenshot, Sequence
from vmtest.i18n import load_localization
from vmtest.image import make_timelapse
from vmtest.vm import VM, Info, QuickEmu, QuickGet


class Runner:
    """
    Runner runs specific tests.
    It also acts as runtime configuration for the test.
    """

    def __init__(
        self,
        output_dir: str,
        osname: str,
        release: str,
        edition: Optional[str],
        variant: Optional[str],
        quickget: bool,
        machine_dir: str,
        quickemu_width: int,
        quickemu_height: int,
    ):
        self.output_dir = output_dir
        self.info = Info(osname, release, edition, variant)
        self.quickget = quickget
        self.machine_dir = machine_dir
        self.quickemu_width = quickemu_width
        self.quickemu_height = quickemu_height
        self._vm: Optional[VM] = None
        os.makedirs(self.machine_dir, mode=0o0775, exist_ok=True)

    @property
    def vm(self) -> VM:
        """
        VM used by the runner.
        """
        if self._vm is not None:
            return self._vm

        if self.quickget:
            self._vm = QuickGet(
                dir=self.machine_dir,
                info=self.info,
                width=self.quickemu_width,
                height=self.quickemu_height,
                reuse_vm=False,
                reuse_disk=False,
                screenshot_dir=os.path.realpath(self.output_dir),
            )
        else:
            self._vm = QuickEmu(
                dir=self.machine_dir,
                info=self.info,
                width=self.quickemu_width,
                height=self.quickemu_height,
                reuse_vm=False,
                reuse_disk=False,
                screenshot_dir=os.path.realpath(self.output_dir),
            )

        return self._vm

    def run(self, commands: list[Command]) -> bool:
        """
        Execute the given commands against the VM.
        :param commands: Commands to execute.
        :return: True if all commands executed successfully.
        """
        os.makedirs("results", exist_ok=True)

        try:
            Sequence(*commands).exec(self.vm)
        except Fail as ex:
            log.error("🚨", ex.message)
            return False
        except KeyboardInterrupt:
            log.error("🚨", "exiting on request")
            return False

        return True

    def store_log(self, dest: str) -> None:
        """
        Store the test log in the given location.

        :param dest: Desired location.
        """
        shutil.copyfile(os.path.join(self.output_dir, "vmtest.log"), dest)

    def store_screenshot(self, dest: str) -> None:
        """
        Create and store a screenshot in the given location.
        :param dest: Desired location.
        """
        screenshot = Screenshot().create(self.vm)
        os.rename(screenshot, dest)

    def remove_results(self) -> None:
        """
        Remove the 'results' directory.
        """
        shutil.rmtree(self.output_dir)

    def remove_vm(self, keep_iso: bool = False) -> None:
        """
        Remove the VM.

        :param keep_iso: Remove everything but the ISO.
        """
        self.vm.power_off()
        self.vm.remove(keep_iso)


def set_locale(name: str) -> None:
    """
    Set the locale used by the test.

    :param name: Name of the locale to use.
    """
    path = Path(sys.argv[0]).resolve()
    while path.parent != Path("/"):
        path = path.parent
        for ext in [".yaml", ".yml"]:
            conf_path = path.joinpath("i18n", name + ext)
            if conf_path.exists():
                load_localization(str(conf_path))
                return


def run(*commands: Command) -> None:
    """
    Run the test suite.

    :param commands: Commands to execute.
    """
    parser = argparse.ArgumentParser(description="Perform a VM test")
    parser.add_argument("os", type=str, help="OS to perform the test for")
    parser.add_argument("release", type=str, help="OS release to perform the test for")
    parser.add_argument(
        "edition",
        type=str,
        nargs="?",
        default=None,
        help="OS edition to perform the test for",
    )
    parser.add_argument(
        "variant",
        type=str,
        nargs="?",
        default=None,
        help="Optional variant of the test",
    )
    parser.add_argument(
        "--machine-dir",
        type=str,
        default=os.environ.get("VMTEST_VM_DIR", "machines"),
        help="The directory to create VMs in",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.environ.get("VMTEST_RESULTS_DIR", ""),
        help="Directory to store output logs and screenshots in (VMTEST_RESULTS_DIR)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=os.environ.get("VMTEST_LANGUAGE", "en_US"),
        help="Language to use for localization",
    )
    parser.add_argument(
        "--save-last-screenshot",
        action="store_true",
        default=getenv_bool("VMTEST_SAVE_LAST_SCREENSHOT", True),
        help="Store the last snapshot (VMTEST_SAVE_LAST_SCREENSHOT)",
    )
    parser.add_argument(
        "--save-timelapse",
        action="store_true",
        default=getenv_bool("VMTEST_SAVE_TIMELAPSE", True),
        help="Store a timelapse (VMTEST_SAVE_TIMELAPSE)",
    )
    parser.add_argument(
        "--keep-results",
        action="store_true",
        default=getenv_bool("VMTEST_KEEP_RESULTS", False),
        help="Keep intermediate results like screenshots (VMTEST_KEEP_RESULTS)",
    )
    parser.add_argument(
        "--keep-vm",
        action="store_true",
        default=getenv_bool("VMTEST_KEEP_VM", False),
        help="Keep the VM data afterwards (VMTEST_REMOVE_VM)",
    )
    parser.add_argument(
        "--remove-iso",
        action="store_true",
        default=getenv_bool("VMTEST_REMOVE_ISO", False),
        help="Also remove the ISO when removing VM data (VMTEST_REMOVE_ISO)",
    )
    parser.add_argument(
        "--skip-quickget",
        action="store_true",
        default=getenv_bool("VMTEST_SKIP_QUICKGET", False),
        help="Skip the quickget step",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    log.setup(args.output_dir)
    set_locale(args.language)

    runner = Runner(
        output_dir=args.output_dir,
        osname=args.os,
        release=args.release,
        edition=args.edition,
        variant=args.variant,
        quickget=not args.skip_quickget,
        machine_dir=args.machine_dir,
        quickemu_width=1920,
        quickemu_height=1080,
    )

    result = runner.run(list(commands))
    if result:
        log.info("✔️", "Test succeeded")
    else:
        log.info("❌", "Test failed")

    if args.save_timelapse:
        log.info("🎥", f"Creating timelapse in {args.output_dir}.mp4")
        make_timelapse(args.output_dir, args.output_dir + ".mp4")

    if args.save_last_screenshot:
        log.info("📸", f"Storing screenshot to {args.output_dir}.png")
        runner.store_screenshot(args.output_dir + ".png")

    if not args.keep_vm:
        log.info("🗑️", "Removing VM data")
        if not args.remove_iso:
            log.info("💿", "Keeping ISO")

        runner.remove_vm(keep_iso=not args.remove_iso)

    runner.store_log(args.output_dir + ".log")

    if not args.keep_results:
        log.info("🗑️", "Removing intermediate results")
        runner.remove_results()

    exit(not result)
