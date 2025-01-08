# vmtest

*VMTest* is a Python project for testing VMs.
It is inspired by [Quicktest] and the internal tooling that used for Solus.
Like Quicktest, it uses [Quickemu] to run virtual machines.

*VMTest* can run both individual test cases or entire test suites with complicated matrices.
It is used by Solus to validate ISOs before release, but can be used for any Linux distro or operating system.

## Usage

On Solus, `vmtest` and its dependencies can be installed through the `vmtest` package.
For other systems, it has the following dependencies:

- Python packages: `pyocr`, `pillow` and `PyYAML`.
- [Quickemu] with `quickemu` and `quickget`
- `ffmpeg`

This repository contains various example suites and tests.
Clone it to get started:

```
git clone https://github.com/getsolus/vmtest.git
cd vmtest
```

`vmtest.py` has the following three main modes of operation:

- List tests:
  ```
  ./vmtest.py -l
  ```
- Run a test suite:
  ```
  ./vmtest.py -s testsuites/alpine/boot_to_login.yaml
  ```
- Run a single test against:
  ```
  ./vmtest.py boot_to_login alpine v3.19
  ```

### Options

VMTest can be configured through environment variables:

| Name                          | Default    | Description                                          |
|-------------------------------|------------|------------------------------------------------------|
| `VMTEST_VM_DIR`               | `machines` | The directory to create VMs in                       |
| `VMTEST_RESULTS_DIR`          | `results`  | Directory to store output logs and screenshots in    |
| `VMTEST_LANGUAGE`             | `en_US`    | Localization to use for translating strings          |
| `VMTEST_SAVE_LAST_SCREENSHOT` | `true`     | Store the last snapshot                              |
| `VMTEST_SAVE_TIMELAPSE`       | `true`     | Store a timelapse                                    |
| `VMTEST_KEEP_RESULTS`         | `false`    | Disable cleanup of screenshot and logging            |
| `VMTEST_KEEP_VM`              | `false`    | Keep the VM data after the test                      |
| `VMTEST_REMOVE_ISO`           | `false`    | Also remove the ISO when removing VM data            |
| `VMTEST_SKIP_QUICKGET`        | `false`    | Skip retrieving the ISO and VM config using Quickget |
| `LOG_LEVEL`                   | `info`     | Configure the log level, eg: `debug`                 |

Additionally, all [Quickemu configuration options] can be set using `VM_{name}`.
The following are generally useful:

| Name            | Description                           |
|-----------------|---------------------------------------|
| `VM_ISO`        | Path to the ISO file                  |
| `VM_BOOT`       | Set VM firmware (`legacy` or `efi`)   |
| `VM_VIEWER`     | Configure viewer (`none` disables)    |
| `VM_SECUREBOOT` | Configure secure boot (`off` or `on`) | 

### Writing tests

Tests are written by creating a string of commands and running them.
They need to start with a comment explaining the test.
For example:

```python3
# Test something I want
from vmtest import run
from vmtest.command import Sleep

run(
  Sleep(1)
)
```

The location of the test in the `testcases` directory determines for which it applies.
This means that a test case in `testcases/alpine` can be used to test all Alpine versions,
but a test case in `testcases/alpine/v3.19` can only be used to test Alpine v3.19.

See the `testcases` directory for various actual test cases.
This includes an example of a localized test in `testcases/alpine/boot_to_login.py`.

Documentation of the available commands is available in you editor or `pydoc` (eg: `python3 -m pydoc vmtest.command`).

### Writing suites

Suites have two sections: `default` that contains defaults for every test,
and `suites` that contain the permutations to be tested.

The following test runs a single test against `bios` and `efi`:

```yaml
# Defaults for all tests.
default:
  test: boot_to_login
  os: alpine

# List of test suites.
# Values are arrays, with all permutations tested.
# The following results in 4 tests:
suites:
  - release: [v3.19, v3.20]
    env:
      VM_BOOT: [legacy, efi]
```

It is possible to use environment variables in the test.
The following sets the ISO to a location set in environment variables:

```yaml
suites:
  - edition: [Budgie]
    env:
      VM_ISO: ["$ISO_BUDGIE"]
  - edition: [Plasma]
    env:
      VM_ISO: ["$ISO_PLASMA"]
```

See the `testsuites` directory for various actual test suites.

## Development

### Building

This project is PEP517 compatible and can be built as such:

```shell
python3 -m build --wheel --sdist
```

[Quickemu]: https://github.com/quickemu-project/quickemu
[Quicktest]: https://github.com/quickemu-project/quicktest
[Quickemu configuration options]: https://github.com/quickemu-project/quickemu/blob/master/docs/quickemu_conf.5.md
