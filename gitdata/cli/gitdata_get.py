"""
usage: gitdata get [options] [<ref>...]

options:
    -h, --help
"""

from pprint import pprint

import gitdata.connectors.common


def get(args):
    if args['<ref>']:
        for ref in args['<ref>']:
            print('getting', ref)
            pprint(
                gitdata.connectors.common.get(ref),
            )
    else:
        print(__doc__)
        print(args)
