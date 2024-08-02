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
            result = gitdata.connectors.common.get(ref)
            if isinstance(result, dict):
                max_len = max(map(len, result.keys())) + 3
                for k, v in result.items():
                    print('%s%s: %s' % (k, '.' * (max_len - len(k)), v))
    else:
        print(__doc__)
        print(args)
