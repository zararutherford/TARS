"""tars-nightly entry point. M-1 placeholder; the nightly job itself is M2 work."""

from __future__ import annotations

import sys

from tars import log


def main() -> None:
    log.configure()
    log.get_logger("tars.nightly").info("tars-nightly is not implemented yet (M2)")
    sys.exit(0)
