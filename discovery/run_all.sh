"""run_all.sh — regenerate the full dataset profile.

Usage:
    bash discovery/run_all.sh

Requires: discovery/.venv with pandas (python3 -m venv discovery/.venv &&
discovery/.venv/bin/pip install pandas). Re-runnable end to end; overwrites
discovery/results/*.json and docs/DATA_DISCOVERY.md. Never touches data/.
"""
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

PY=discovery/.venv/bin/python
if [ ! -x "$PY" ]; then
  PY=python3
fi
export PYTHONPATH=discovery

for step in 01_inventory 02_schema 03_duplicates 04_numeric 05_target_valuation \
            06_transfers 07_categoricals 08_referential 09_temporal 10_quality; do
  echo "=== $step ==="
  "$PY" "discovery/$step.py"
done

echo "=== render_report ==="
"$PY" discovery/render_report.py
echo "Done: docs/DATA_DISCOVERY.md"
