#!/usr/bin/env bash
# Find a working Python 3 interpreter and exec the hook with it.
#
# On Windows + Git Bash, `python3` typically resolves to the Microsoft Store
# stub at C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python3, which
# exits 49 silently in non-TTY subprocess context (a known Microsoft Store
# stub behavior). This shim probes each candidate with `-c ""` and skips any
# that fails, so the Store stub falls through to the real python.org install
# (`python` in Git Bash) or the `py -3` launcher.
#
# Order:
#   1. python3   — canonical on macOS/Linux; the Store stub fails the probe.
#   2. python    — python.org installs on Windows; some Linux distros point
#                  this at Python 2 — guard with a version check.
#   3. py -3     — Windows Python launcher.
#
# Args after the shim path are passed straight through to the chosen
# interpreter, so invocation is:
#   bash "/path/to/python_finder.sh" "/path/to/comm_review.py"
set -e

# Git Bash / MSYS on Windows hands script paths to this shim in POSIX form
# (`/c/Users/...`). When we exec a Windows `python.exe` (which we do on
# Windows since `python3` is the Microsoft Store stub), python interprets the
# leading `/` as the root of the current drive, causing ENOENT.
# Fix: convert absolute path args to native Windows form via `cygpath -w`.
# `cygpath` is a Git Bash builtin; absent on macOS/Linux so the guard is a no-op.
if command -v cygpath >/dev/null 2>&1; then
    converted=()
    for a in "$@"; do
        case "$a" in
            /*) converted+=("$(cygpath -w "$a" 2>/dev/null || echo "$a")") ;;
            *)  converted+=("$a") ;;
        esac
    done
    set -- "${converted[@]}"
fi

probe() {
    "$@" -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

for cmd in "python3" "python" "py -3"; do
    # shellcheck disable=SC2086
    probe $cmd || continue
    # shellcheck disable=SC2086
    exec $cmd "$@"
done

echo "comm-review: no working Python 3.10+ interpreter found." >&2
echo "  tried: python3, python, py -3" >&2
echo "  on Windows, install Python 3.10+ from https://python.org (NOT the Microsoft Store)" >&2
exit 1
