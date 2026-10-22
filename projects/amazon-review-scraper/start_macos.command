#!/bin/bash
# Compatible with the Bash shipped with macOS; paths and arguments stay quoted.
cd "$(dirname "$0")" || exit 1
toolkit_python=""
if [ -x ".venv/bin/python" ]; then
    toolkit_python=".venv/bin/python"
else
    for candidate in python3 python3.12 python3.11 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys,struct;sys.exit(0 if sys.version_info >= (3,10) and struct.calcsize("P") == 8 else 1)' >/dev/null 2>&1; then
            toolkit_python="$candidate"
            break
        fi
    done
fi
if [ -z "$toolkit_python" ]; then
    echo "Please install 64-bit Python 3.11 or 3.12, then run this file again."
    echo "https://www.python.org/downloads/macos/"
    echo "See README.md or README.en.md for instructions."
    toolkit_exit_code=1
else
    "$toolkit_python" launcher.py "$@"
    toolkit_exit_code=$?
fi
if [ "$toolkit_exit_code" -ne 0 ] && [ -t 0 ] && [ -z "${CI:-}" ]; then
    read -r -p "Press Return to close / 按回车关闭… " toolkit_reply
fi
exit "$toolkit_exit_code"
