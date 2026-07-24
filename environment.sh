#!/bin/bash
# Source this to set up environment variables and aliases for CAIRN development
# Usage: source environment.sh

CAIRN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_ENV_ROOT="$(dirname "$CAIRN_ROOT")"

export PETTA_ROOT="$DEV_ENV_ROOT/PeTTa"
export METTA_ATTENTION_ROOT="$DEV_ENV_ROOT/metta-attention"
export HYPERON_EXP_ROOT="$DEV_ENV_ROOT/hyperon-experimental"
export CAIRN_ROOT="$CAIRN_ROOT"

# Navigation aliases
alias petta="cd $PETTA_ROOT"
alias attention="cd $METTA_ATTENTION_ROOT"
alias hyperon="cd $HYPERON_EXP_ROOT"
alias cairn="cd $CAIRN_ROOT"

# Run aliases
# Append --watch to auto-launch the live dashboard (http://localhost:8501) for that run,
# e.g. `cairn-mve --watch`. Without it, no dashboard/browser activity happens at all.
_cairn_run() {
  local metta_file="$1"; shift
  cd "$CAIRN_ROOT" && source venv/bin/activate
  if [[ " $* " == *" --watch "* ]]; then
    CAIRN_WATCH=1 "$PETTA_ROOT/run.sh" "$metta_file"
  else
    "$PETTA_ROOT/run.sh" "$metta_file"
  fi
}
alias cairn-demo="_cairn_run demo.metta"
alias cairn-mve="_cairn_run mve.metta"
alias cairn-assignment="_cairn_run assignment.metta"
alias cairn-test="cd $CAIRN_ROOT && source venv/bin/activate && for t in $CAIRN_ROOT/dev-tests/test_*.metta; do echo \"=== \$(basename \$t) ===\" && $PETTA_ROOT/run.sh \"\$t\" 2>&1 | grep -E 'PASS|FAIL'; done"

echo "CAIRN environment configured."
echo "  \$CAIRN_ROOT            = $CAIRN_ROOT"
echo "  \$PETTA_ROOT            = $PETTA_ROOT"
echo "  \$METTA_ATTENTION_ROOT  = $METTA_ATTENTION_ROOT"
echo "  \$HYPERON_EXP_ROOT      = $HYPERON_EXP_ROOT"
echo ""
echo "Aliases: cairn, petta, attention, hyperon, cairn-demo, cairn-mve, cairn-assignment, cairn-test"
echo "  Add --watch to any cairn-* run alias to auto-launch the live dashboard (http://localhost:8501)"
