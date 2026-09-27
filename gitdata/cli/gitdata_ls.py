"""
usage: gitdata ls [options] <ref>

options:
    -h, --help      show help
"""

from gitdata.connectors import fetch
from gitdata.inspection import list_items


def ls_to_console(args):
    """List immediate children directly from Connector output."""
    root = fetch(args['<ref>'])
    for item in list_items(root):
        print(item['name'])
