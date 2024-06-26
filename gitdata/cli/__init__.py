"""
usage: gitdata [options] <command> [<args>...]

options:
    -h, --help      show help
    -V, --version   print version
    -d, --debug     debug

The most commonly used gitdata commands are:
    fetch       fetch data to the local reposotiry
    get         get data
    scan        scan data

See 'gitdata help <command>' for more information on a specific command.
"""

import logging

from docopt import docopt
import sys

import gitdata
from gitdata.utils import trim


root_logger = logging.getLogger()


def print_help(doc):
    """Print help text"""
    print(trim(doc))


def main():
    """CLI main"""

    if len(sys.argv) == 1:
        print_help(__doc__)
        sys.exit()

    args = docopt(
        __doc__,
        version='gitdata version {}'.format(gitdata.__version__),
        options_first=True
    )

    if args['--debug']:
        print(args)
        root_logger.setLevel(logging.DEBUG)

    argv = [args['<command>']] + args['<args>']

    if args['<command>'] == 'get':
        from gitdata.cli.gitdata_get import get, __doc__ as doc
        args = docopt(doc, argv=argv)
        get(args)

    elif args['<command>'] == 'scan':
        from gitdata.cli.gitdata_scan import scan_to_console, __doc__ as doc
        args = docopt(doc, argv=argv)
        scan_to_console(args)

    elif args['<command>'] in ['help', None]:
        if args['<args>'] == ['get']:
            from gitdata.cli.gitdata_get import __doc__ as doc
            exit(doc)
        exit(__doc__)

    else:
        exit("%r is not a gitdata command. See 'gitdata help'." % args['<command>'])
