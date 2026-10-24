# rc.sh -- source me. `run <cmd...>` captures the PROCESS exit status, never a pipeline member's.
#
# Six 1s.4 violations in this campaign were `cmd | tail -n N; echo rc=$?`, every one correct-looking at
# the moment it was typed. An invariant broken six times is a wish, not a rule, so the shape changes:
#   . tools/rc.sh
#   run tools/x.py --flag          # prints the process rc, and `run ... && ...` propagates it
#
# A pipeline passed as words is REFUSED rather than silently mis-measured -- the failure this exists to
# prevent must not be reproducible by accident.
run() {
    case "$1" in *'|'*|*';'*|*'&&'*) echo "rc.sh: refusing a shell string ('$1') -- pass argv, let run do the redirecting" >&2; return 2;; esac
    _rc_out="${RC_OUT:-/tmp/rc.out}"
    "$@" >"$_rc_out" 2>&1
    _rc=$?
    [ -n "${RC_TAIL:-}" ] && tail -n "$RC_TAIL" "$_rc_out"
    echo "rc=$_rc"
    return $_rc
}
