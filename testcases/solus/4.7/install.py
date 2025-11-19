# Test installation using SOLUS_FS, SOLUS_SWAP and SOLUS_LUKS environment vars
import os
import vmtest

from testcases.solus._common import Solus

if __name__ == "__main__":
    s = Solus(
        fs=os.environ.get("SOLUS_FS") or "default",
        swap=os.environ.get("SOLUS_SWAP") or "default",
        luks=bool(os.environ.get("SOLUS_LUKS") or False),
    )
    vmtest.run(
        s.install(),
        s.boot_to_desktop(),
        s.show_info_terminal(),
    )
