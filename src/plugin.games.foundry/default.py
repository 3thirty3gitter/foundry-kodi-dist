"""Kodi plugin entry point. Importing this module does not start a scan."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
from kodi_ui import run

if __name__ == '__main__':
    run(sys.argv)
