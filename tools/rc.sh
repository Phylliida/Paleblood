# rc.sh -- source me. `run <argv...>` captures the PROCESS exit status, never a pipeline member's.
#
# Six 1s.4 violations in this campaign were `cmd | tail -n N; echo rc=$?`, every one correct-looking at the
# moment it was typed. An invariant broken six times is a wish, not a rule, so the shape changes:
#   . tools/rc.sh
#   run tools/x.py --flag          # prints the process rc; `run ... && ...` propagates it
#
# The refusal is a WHITELIST, not a list of pipes. The first version named `|`, `;` and `&&` -- three members
# of a character class -- while `$(...)`, backticks, `>`, `<` and `&` all remained reachable, so the seventh
# violation would have arrived through a character the check did not name and would have looked correct when
# typed. An argument is accepted only if EVERY character is in the allowed class below; anything else is
# refused with the offending character printed.
_rc_allowed='A-Za-z0-9 _./:=+,-'

_rc_refuse() {   # rc_refuse <arg>  -> prints why and returns 1 if the arg holds a character outside the class
    case "$1" in
        *[!A-Za-z0-9\ _./:=+,-]*) ;;
        *) return 0 ;;
    esac
    _bad=$(printf '%s' "$1" | tr -d "A-Za-z0-9 _./:=+,-" | cut -c1)
    echo "rc.sh: refusing '$1': '${_bad:-?}' is outside the allowed class [${_rc_allowed}]" >&2
    echo "rc.sh: pass argv (run tool --flag), never a shell string; let run do the redirecting" >&2
    return 1
}

run() {
    [ "$#" -gt 0 ] || { echo "rc.sh: run needs a command" >&2; return 2; }
    for _a in "$@"; do _rc_refuse "$_a" || return 2; done
    _rc_out="${RC_OUT:-/tmp/rc.out}"
    "$@" >"$_rc_out" 2>&1
    _rc=$?
    # 126 (not executable) and 127 (not found) are TRANSPORT answers: they say the instrument was absent, not
    # that the subject failed. rc 127 from a missing /bin/true said nothing about the test being run, the same
    # read as BB_PBBOOT defaulting to a stale binary. A precondition is rc 3 everywhere else in this tree, so
    # "not found" can never be quoted as "failed".
    if [ "$_rc" -eq 126 ] || [ "$_rc" -eq 127 ]; then
        echo "rc.sh: $_rc is a precondition failure (command absent or not executable) -- this says nothing about the subject; reporting 3" >&2
        _rc=3
    elif [ "$_rc" -gt 128 ]; then
        echo "rc.sh: note: $_rc = signal $((_rc - 128)); the subject was killed, not merely unsuccessful" >&2
    fi
    [ -n "${RC_TAIL:-}" ] && tail -n "$RC_TAIL" "$_rc_out"
    echo "rc=$_rc"
    return $_rc
}
