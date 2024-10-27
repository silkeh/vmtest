import argparse
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from vmtest._log import setup as log_setup
from vmtest._util import getenv_bool
from vmtest.command import Command, Fail, Screenshot, Sequence
from vmtest.i18n import load_localization
from vmtest.image import make_timelapse
from vmtest.vm import VM, Info, QuickEmu, QuickGet


class Runner:
    """
    Runner runs specific tests.
    It also acts as runtime configuration for the test.
    It is initialized using environment variables.
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
        os.makedirs("results", exist_ok=True)

        try:
            Sequence(*commands).exec(self.vm)
        except Fail as ex:
            print(f"🚨 {ex.message}")
            return False
        except KeyboardInterrupt:
            print("🚨 exiting on request")
            return False

        return True

    def store_log(self, dest: str) -> None:
        shutil.copyfile(os.path.join(self.output_dir, "vmtest.log"), dest)

    def store_screenshot(self, dest: str) -> None:
        screenshot = Screenshot().create(self.vm)
        os.rename(screenshot, dest)

    def remove_results(self) -> None:
        shutil.rmtree(self.output_dir)

    def remove_vm(self, keep_iso: bool = False) -> None:
        self.vm.power_off()
        self.vm.remove(keep_iso)


def set_locale(name: str) -> None:
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

    :param commands:
    :return:
    """
    logging.basicConfig(
        level=logging.getLevelName(os.environ.get("LOG_LEVEL", "info").upper()),
        format="%(message)s",
    )

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
    log_setup(args.output_dir)
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

    if not runner.run(list(commands)):
        logging.info("ℹ️ VM and intermediate results have not been removed")
        exit(1)

    if args.save_timelapse:
        logging.info(f"🎥 Creating timelapse in {args.output_dir}.mp4")
        make_timelapse(args.output_dir, args.output_dir + ".mp4")

    if args.save_last_screenshot:
        logging.info(f"📸 Storing screenshot to {args.output_dir}.png")
        runner.store_screenshot(args.output_dir + ".png")

    if not args.keep_vm:
        logging.info("🗑️  Removing VM data")
        if not args.remove_iso:
            logging.info("💿 Keeping ISO")

        runner.remove_vm(keep_iso=not args.remove_iso)

    runner.store_log(args.output_dir + ".log")

    if not args.keep_results:
        logging.info("🗑️  Removing intermediate results")
        runner.remove_results()
