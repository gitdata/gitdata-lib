"""
usage: gitdata [-V | --version] [-v | --verbose] [-d | --debug] [--help] <command> [<args>...]

The most commonly used gitdata commands are:
   help       Show help

See 'gitdata help <command>' for more information on a specific command.
"""

import docopt
import gitdata

from gitdata.utils import trim


def print_help(doc):
    """Print help text"""
    print(trim(doc))


def main():
    """CLI main"""

    args = docopt.docopt(
        __doc__,
        version='gitdata version {}'.format(gitdata.__version__),
        options_first=True
    )

    if args['<command>'] == 'help':
        topic = next(iter(args['<args>']), None)

        if topic == 'help':
            print_help(__doc__)
        elif topic:
            exit("%r is not a gitdata command. See 'gitdata help'." % topic)
        else:
            exit(__doc__)
