"""
usage: gitdata [options] <command> [<args>...]

options:
    -h, --help      show help
    -V, --version   print version
    -d, --debug     debug

The most commonly used gitdata commands are:
    init        initialize a local gitdata repository
    fetch       fetch data to the local reposotiry
    get         get data
    scan        scan data

See 'gitdata help <command>' for more information on a specific command.
"""

import importlib
import logging
import sys

from docopt import docopt

import gitdata
from gitdata.utils import trim


root_logger = logging.getLogger()


def print_help(doc):
    """Print help text"""
    print(trim(doc))


def get_module_doc(name):
    module_name = 'gitdata.cli.gitdata_' + name
    try:
        result = importlib.import_module(module_name).__doc__
    except ModuleNotFoundError:
        result = f'no help on topic {name!r}'
    return result


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
    command = args['<command>']

    if command == 'help':
        if args['<args>']:
            topic = args['<args>'][0]
            doc = get_module_doc(topic)
        else:
            doc = __doc__
        print_help(doc)
        sys.exit()

    elif command == 'init':
        from gitdata.cli.gitdata_init import init, __doc__ as doc
        args = docopt(doc, argv=argv)
        init(args)

    elif command == 'get':
        from gitdata.cli.gitdata_get import get, __doc__ as doc
        args = docopt(doc, argv=argv)
        get(args)

    elif command == 'scan':
        from gitdata.cli.gitdata_scan import scan_to_console, __doc__ as doc
        args = docopt(doc, argv=argv)
        scan_to_console(args)

    else:
        exit("%r is not a gitdata command. See 'gitdata help'." % args['<command>'])
