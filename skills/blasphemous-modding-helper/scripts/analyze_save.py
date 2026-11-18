#!/usr/bin/env python3
"""Analyze one explicit Blasphemous 1 save file or directory read-only."""

import sys

sys.dont_write_bytecode = True

from save_analysis import main


if __name__ == "__main__":
    raise SystemExit(main())
