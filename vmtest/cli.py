#!/usr/bin/env python3
import argparse
import hashlib
import logging
import os.path
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from string import Template
from typing import Any, Optional

import yaml

from vmtest._log import setup as log_setup
from vmtest._util import list_values


def sub(s: str) -> str:
    """
    Replace variables in the given string by their environment variable value.

    :param s: String to substitute in.
    :return: Resulting string.
    """
    return Template(str(s)).safe_substitute(**os.environ)


def subn(s: Optional[str]) -> Optional[str]:
    """
    Replace variables in the given string by their environment variable value.

    :param s: String to substitute in or None if the value is optional.
    :return: Resulting string or None if given value is None.
    """
    return sub(s) if s is not None else None


def _dict_diff(a: dict[str, str], b: Optional[dict[str, str]]) -> dict[str, str]:
    c = a.copy()
    if b is None:
        return c

    for k, v in b.items():
        if v == c.get(k):
            del c[k]

    return c


def _env_str(env: dict[str, str], defaults: Optional[dict[str, str]]) -> str:
    return "; ".join([f"{k}={v}" for k, v in _dict_diff(env, defaults).items()])


@dataclass
class TestCase:
    """
    A discovered test case.
    """

    os: str
    release: str
    edition: str
    name: str
    desc: str

    @staticmethod
    def from_file(root: Path, file: Path) -> "TestCase":
        """
        Initialize a TestCase from a file.

        :param root: Directory in which the file is located.
        :param file: File to load.
        :return: Decoded test case.
        """
        dirs = str(file.relative_to(root)).split(os.path.sep)

        with open(file, "r") as fh:
            desc = fh.readline().strip().removeprefix("# ")
            name, _ = os.path.splitext(file.name)
            osname = dirs[0]
            release = dirs[1] if len(dirs) == 3 else "*"
            edition = dirs[2] if len(dirs) == 4 else "*"

            return TestCase(osname, release, edition, name, desc)

    def tuple(self) -> tuple[str, str, str, str, str]:
        """
        Return a tuple containing the components of the test case.

        :return: quintuple containing os, release, edition, name and description.
        """
        return self.os, self.release, self.edition, self.name, self.desc


def __max_cols(cases: list[TestCase]) -> tuple[int, ...]:
    return tuple([len(max(c, key=len)) for c in zip(*[list(c.tuple()) for c in cases])])


def __list_testcases(path: Path) -> None:
    cases: list[TestCase] = [
        TestCase("OS", "Release", "Edition", "Test name", "Description")
    ]

    for dir_path, _, files in os.walk(path):
        if len(files) == 0 or len(dir_path.split(os.path.sep)) < 2:
            continue

        for filename in files:
            _, ext = os.path.splitext(filename)
            if filename.startswith("_") or ext != ".py":
                continue

            cases.append(
                TestCase.from_file(Path(path), Path(dir_path).joinpath(filename))
            )

    os_size, rel_size, ed_size, name_size, _ = __max_cols(cases)
    for case in cases:
        print(
            case.os.ljust(os_size),
            case.release.ljust(rel_size),
            case.edition.ljust(ed_size),
            case.name.ljust(name_size),
            case.desc,
            sep="  ",
        )


@dataclass
class Test:
    """
    A test to execute.
    """

    name: str
    os: str
    release: str
    edition: Optional[str]
    env: dict[str, str]
    ts: Optional[datetime]

    def __post_init__(self) -> None:
        if self.env is None:
            self.env = {}

    def __str__(self) -> str:
        env_str = ""
        edition_str = ""

        if self._env_without_vmtest():
            env_str = f" (env: {self._env_without_vmtest()})"

        if self.edition is not None:
            edition_str = f" {self.edition}"

        return f"Test({self.name} {self.os} {self.release}{edition_str}{env_str})"

    def _env_without_vmtest(self) -> dict[str, str]:
        return {k: v for k, v in self.env.items() if not k.startswith("VMTEST_")}

    def dry_run(self, root_path: Path, output_dir: Path) -> None:
        """
        Show what would be executed instead of running the test.

        :param root_path: Directory containing the test cases.
        :param output_dir: Directory to store results in.
        """
        args, env = self._command(root_path, output_dir)
        cmd = " ".join(args)
        logging.info(f"Would execute {repr(cmd)}, env: {env}")

    def run(self, root_path: Path, output_dir: Path) -> bool:
        """
        Run the test.

        :param root_path: Directory containing the test cases.
        :param output_dir: Directory to store results in.
        """
        args, env = self._command(root_path, output_dir)

        return subprocess.run(args=args, env=env).returncode == 0

    def output_dir(self, root: Path = Path(".")) -> Path:
        """
        Return the output directory for this test.
        It returns a relative path by default.

        :param root: Directory in which all results are stored.
        :return: Given directory extended by the test properties.
        """
        components = [
            self.os,
            self.release,
            self.edition or None,
            self._env_str() or None,
            self.name,
            self.ts.isoformat(timespec="seconds") if self.ts else None,
        ]

        return root.joinpath(*list_values(components))

    def _env_str(self) -> str:
        if len(self.env) == 0:
            return ""

        m = hashlib.sha256()
        for k, v in self.env.items():
            m.update(f"{k}={v}".encode())

        return "variant_" + m.hexdigest()

    def _command(
        self, root: Path, output_dir: Path
    ) -> tuple[list[str], dict[str, str]]:
        env = os.environ.copy()
        env.update(self._resolved_env())
        env["PYTHONPATH"] = self._python_path(root)

        logging.debug(f'Python path: {env["PYTHONPATH"]}')

        args = [
            "python3",
            self._path(root),
            self.os,
            self.release,
            self.edition,
            "--output-dir",
            self.output_dir(output_dir),
        ]

        return list_values(args), env

    def _path(self, root: Path) -> Path:
        components = [self.os, self.release, str(self.edition)]

        while len(components) > 0:
            path = root.joinpath(*components, self.name + ".py")
            if path.exists():
                return path

            components = components[0:-1]

        raise FileNotFoundError(f"Test {repr(self.name)} could not be found")

    def _resolved_env(self) -> dict[str, str]:
        return {k: str(sub(v)) for k, v in self.env.items()}

    @staticmethod
    def _python_path(root: Path) -> str:
        path = [os.environ.get("PYTHONPATH", None), root.parent.resolve()]

        if Path(__file__).parent.joinpath("vmtest").exists():
            path.append(Path(__file__).parent.resolve())

        return os.pathsep.join([str(p) for p in list_values(path)])


@dataclass
class SuiteDefaults:
    """
    Default values for the test suites.
    """

    test: Optional[str] = None
    os: Optional[str] = None
    release: Optional[str] = None
    edition: Optional[str] = None
    env: Optional[dict[str, str]] = None


@dataclass
class Suite:
    """
    A suite of tests to execute.
    """

    test: Optional[list[str]] = None
    os: Optional[list[str]] = None
    release: Optional[list[str]] = None
    edition: Optional[list[Optional[str]]] = None
    env: Optional[dict[str, list[str]]] = None

    def all(self, default: SuiteDefaults) -> list[Test]:
        """
        Get a list of all tests that are covered by this suite.

        :param default: Default values to use for the suite.
        :return: List of tests in the suite.
        """
        return [
            Test(
                name=sub(name),
                os=sub(osname),
                release=sub(release),
                edition=subn(edition),
                env=env,
                ts=None,
            )
            for name in (self.test or [str(default.test)])
            for osname in (self.os or [str(default.os)])
            for release in (self.release or [str(default.release)])
            for edition in (self.edition or [default.edition])
            for env in self._envs(default.env or {})
        ]

    def _envs(self, default: dict[str, str]) -> list[dict[str, str]]:
        env = self.env or {}

        return [
            {**default, **dict(zip(env.keys(), values))}
            for values in product(*[v for v in env.values()])
        ]


class Suites:
    """
    Complete test suite configuration with defaults and a list of test suites to execute.
    """

    def __init__(self, name: str, data: Any, path: Path, output: Path):
        """
        Initialize the test suites from configuration data.

        :param name: Name of the config.
        :param data: Configuration from YAML.
        :param path: Path containing test cases.
        :param output: Path to store results in.
        """
        self.name = name
        self.default = SuiteDefaults(**data.get("default", {}))
        self.suites = [Suite(**s) for s in data["suites"]]
        self.path = path
        self.ts = datetime.now().astimezone()
        self.output = output.joinpath(name, self.ts.isoformat(timespec="seconds"))
        self.index = self.output.joinpath("index.html")
        os.makedirs(self.output, mode=0o0775, exist_ok=True)

    def all(self) -> list[Test]:
        """
        Get a list of all tests that are covered by this suite.

        :return: List of tests in the suite.
        """
        return [test for suite in self.suites for test in suite.all(self.default)]

    def run(self) -> None:
        """
        Run all tests in sequence.
        """
        self.__start_html()

        for test in self.all():
            start = datetime.now(UTC)
            logging.info(f"▶️  {test}")
            result = test.run(self.path, self.output)
            duration = datetime.now(UTC) - start
            logging.info(f"{self.__result_icon(result)} {test}")
            logging.info(f"⏱️  Test took {duration}")

            self.__test_html(test, result, duration)

        logging.info(
            f"✅ Suite completed. Results are stored in file://{os.path.realpath(self.output)}"
        )
        self.__end_html()

    def __start_html(self) -> None:
        logging.info(f"🌐 Test suite overview: file://{os.path.realpath(self.index)}")

        with open(self.index, "w") as fh:
            fh.write(
                "<!DOCTYPE html>"
                "<html lang=en-gb>"
                "<head>"
                f"<title>Test suite {repr(self.name)} ({self.ts})</title>"
                "<meta charset=utf-8>"
                "<style>"
                "  body {font-family: sans-serif; }"
                "  table, th, td { border: 1px solid gray; border-collapse: collapse; }"
                "  td { padding: 0.2em }"
                "</style>"
                "</head>"
                "<body>"
                f"<h1>Suite: {self.name}</h1>"
                f"<p>Started at {self.ts}</p>"
                "<h2>Results</h2>"
                "<table>"
                "<tr>"
                "<th>🧪</th><th>Test</th>"
                "<th>OS</th><th>Release</th><th>Edition</th><th>Environment</th>"
                "<th>📷</th><th>🎥</th><th>📝</th><th>⏱️</th>"
                "</tr>"
            )

    def __end_html(self) -> None:
        logging.info(f"🌐 Test suite overview: file://{os.path.realpath(self.index)}")
        with open(self.index, "a") as fh:
            fh.write("</table></body></html>")

    def __test_html(self, test: Test, result: bool, duration: timedelta) -> None:
        duration = timedelta(
            days=duration.days, seconds=duration.seconds, microseconds=0
        )

        img_str = ""
        if bool(self.__getenv("VMTEST_SAVE_LAST_SCREENSHOT", "True")):
            img_str = (
                f'<a href="{test.output_dir()}.png">'
                f'<img style="height:2em" src="{test.output_dir()}.png" alt="🖼️"/>'
                "</a>"
            )

        video_str = ""
        if bool(self.__getenv("VMTEST_SAVE_TIMELAPSE", "True")):
            video_str = f'<a href="{test.output_dir()}.mp4">▶️</a>'

        with open(self.index, "a") as fh:
            fh.write(
                "<tr>"
                f"<td>{self.__result_icon(result)}</td>"
                f"<td>{test.name}</td>"
                f"<td>{test.os}</td>"
                f"<td>{test.release}</td>"
                f"<td>{test.edition}</td>"
                f"<td>{_env_str(test.env, self.default.env)}</td>"
                f"<td>{img_str}</td>"
                f"<td>{video_str}</td>"
                f'<td><a href="{test.output_dir()}.log">📃</a></td>'
                f"<td>{duration}</td>"
                "</tr>"
            )

    def __getenv(self, key: str, default: Optional[str] = None) -> Optional[str]:
        if key in os.environ:
            return os.environ[key]

        if self.default.env is not None and key in self.default.env:
            return self.default.env[key]

        return default

    @staticmethod
    def __result_icon(value: bool) -> str:
        return "✅" if value else "❌"


def main() -> None:
    """
    Main function of the CLI.
    """
    parser = argparse.ArgumentParser(description="Perform a VM test")
    parser.add_argument(
        "name", type=str, default="", nargs="?", help="Name of the test to run"
    )
    parser.add_argument(
        "os", type=str, default="", nargs="?", help="OS to perform the test for"
    )
    parser.add_argument(
        "release",
        type=str,
        default="",
        nargs="?",
        help="OS release to perform the test for",
    )
    parser.add_argument(
        "edition",
        type=str,
        default="",
        nargs="?",
        help="OS edition to perform the test for",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available tests instead of running them",
    )
    parser.add_argument("-s", "--suite", type=str, help="Run the given test suite")
    parser.add_argument(
        "-t",
        "--testcase-dir",
        type=str,
        default="testcases",
        help="Directory containing test cases",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="results",
        help="Directory to store test output in",
    )
    parser.add_argument(
        "-m",
        "--machine-dir",
        type=str,
        default="machines",
        help="Directory to store VMs in",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()
    if args.debug:
        os.environ["LOG_LEVEL"] = "debug"

    os.environ["VMTEST_VM_DIR"] = args.machine_dir

    if args.list:
        __list_testcases(Path(args.testcase_dir))
        exit(0)

    if args.suite:
        with open(args.suite, "rb") as f:
            name, _ = os.path.splitext(os.path.basename(args.suite))
            suites = Suites(
                name=name,
                data=yaml.safe_load(f),
                path=Path(args.testcase_dir),
                output=Path(args.output_dir),
            )
            log_setup(suites.output)
            suites.run()
            exit(0)

    if not args.name:
        parser.print_help()
        exit(1)

    test = Test(
        name=args.name,
        os=args.os,
        release=args.release,
        edition=args.edition,
        env={},
        ts=datetime.now().astimezone(),
    )

    log_setup(test.output_dir(Path(args.output_dir)))
    test.run(Path(args.testcase_dir), Path(args.output_dir))
