"""tars-llm entry point. M-1 placeholder; the server itself is M0 work."""

from __future__ import annotations

import sys

from tars import log


def main() -> None:
    log.configure()
    log.get_logger("tars.llm").info("tars-llm is not implemented yet (M0)")
    sys.exit(0)
