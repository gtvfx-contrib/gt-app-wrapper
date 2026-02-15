"""Main entry point for running the wrapper as a module.

Usage:
    python -m gt.app.wrapper [command] [args...]
    python -m gt.app.wrapper --list
    python -m gt.app.wrapper --info <command>
    
"""

import sys
from ._cli import main


if __name__ == '__main__':
    sys.exit(main())
