"""Main entry point for running envoy as a module.

Usage:
    python -m gt.envoy [command] [args...]
    python -m gt.envoy --list
    python -m gt.envoy --info <command>
    
"""

import sys
from ._cli import main


if __name__ == '__main__':
    sys.exit(main())
