#!/usr/bin/env bash
set -euo pipefail
bash tests/equivalence/run_source.sh
bash tests/equivalence/run_role.sh
echo "=== DIFF source vs role ==="
if diff -u /tmp/source_state.txt /tmp/role_state.txt; then
  echo "ÉQUIVALENT : état final identique."
else
  echo "DIVERGENCE : voir diff ci-dessus."; exit 1
fi
