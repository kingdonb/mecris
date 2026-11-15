#!/usr/bin/env python3
"""Claude Code status line command: record plan usage, print '5h 16% · wk 24%'.

Configure it in ~/.claude/settings.json:

    "statusLine": {"type": "command", "command": "/usr/bin/python3 /path/to/mecris/scripts/claude_statusline.py"}

It reads the status line JSON on stdin and writes the plan windows to
~/.claude/usage.json (override with CLAUDE_USAGE_SNAPSHOT). See
claude_statusline.py at the repository root for the logic.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    try:
        from claude_statusline import main
    except Exception:
        print("plan usage: waiting")
        sys.exit(0)
    sys.exit(main())
