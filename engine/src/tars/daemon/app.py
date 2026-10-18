"""tars-daemon entry point. M-1 placeholder; the daemon itself is M1 work."""

from __future__ import annotations

import sys

from tars import log


def main() -> None:
    log.configure()
    log.get_logger("tars.daemon").info("tars-daemon is not implemented yet (M1)")
    sys.exit(0)
