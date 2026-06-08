#!/usr/bin/env bash
# Proves the validator passes a valid fixture and fails a deliberately-broken one
# with the expected diagnostics. Run from anywhere.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
V=("$PY" "$ROOT/tools/validate.py"); fail=0

echo "[1/2] valid fixture must PASS"
if "${V[@]}" "$ROOT/tests/fixtures/valid_sample.json" >/tmp/cv.out 2>&1; then echo "  OK"
else echo "  FAIL on valid fixture"; cat /tmp/cv.out; fail=1; fi

echo "[2/2] broken fixture must FAIL with expected diagnostics"
"${V[@]}" "$ROOT/tests/fixtures/broken_sample.json" >/tmp/cb.out 2>&1; rc=$?
if [ $rc -eq 0 ]; then echo "  FAIL: broken fixture passed"; cat /tmp/cb.out; fail=1
else
  for n in "duplicate id" "unresolved route" "unknown variable" "interpretation_note" "needs_review"; do
    grep -qi "$n" /tmp/cb.out || { echo "  MISSING diagnostic: $n"; fail=1; }
  done
  [ $fail -eq 0 ] && echo "  OK (exit $rc; all diagnostics present)"
fi

[ $fail -eq 0 ] && { echo "SELFTEST: PASS"; } || { echo "SELFTEST: FAIL"; exit 1; }
