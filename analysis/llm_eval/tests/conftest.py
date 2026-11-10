"""Make `analysis/llm_eval/` importable as top-level modules for the test run.

The scripts are run as `uv run python ../analysis/llm_eval/<script>.py`, so they import
`harness` and `cases_*` as top-level names rather than as a package; the tests mirror
that by putting the parent directory on `sys.path`.
"""

from __future__ import annotations

import sys
from pathlib import Path

LLM_EVAL_DIR = Path(__file__).resolve().parents[1]
if str(LLM_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(LLM_EVAL_DIR))
