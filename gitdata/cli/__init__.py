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
    ls          list immediate children of a ref
    scan        scan data
    secret      manage repository secrets

See 'gitdata help <command>' for more information on a specific command.
"""

import importlib
import logging
import sys

from docopt import docopt

import gitdata
from gitdata.connectors.common import ConnectorError
from gitdata.utils import trim


root_logger = logging.getLogger()


def _redact_inline_url_password(value):
    scheme_end = value.find('://')
    if scheme_end < 1:
        return value
    authority_start = scheme_end + 3
    separators = [
        position for position in (
            value.find('/', authority_start),
            value.find('?', authority_start),
            value.find('#', authority_start),
        )
        if position >= 0
    ]
    authority_end = min(separators) if separators else len(value)
    authority = value[authority_start:authority_end]
    at = authority.rfind('@')
    colon = authority.find(':')
    if at < 0 or colon < 0 or colon > at:
        return value
    redacted = authority[:colon + 1] + '***' + authority[at:]
    return value[:authority_start] + redacted + value[authority_end:]


def _redact_debug_value(value):
    """Remove URL passwords before rendering parsed debug arguments."""
    if isinstance(value, str):
        return _redact_inline_url_password(value)
    if isinstance(value, list):
        return [_redact_debug_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_debug_value(item) for item in value)
    if isinstance(value, dict):
        return {
            key: _redact_debug_value(item)
            for key, item in value.items()
        }
    return value


def terminal_text(value):
    """Render text without terminal control characters."""
    return ''.join(
        character
        if character.isprintable()
        else character.encode('unicode_escape').decode('ascii')
        for character in str(value)
    )


def print_help(doc):
    """Print help text"""
    print(trim(doc))


def get_module_doc(name):
    if name == 'secret':
        name = 'secrets'
    module_name = 'gitdata.cli.gitdata_' + name
    try:
        result = importlib.import_module(module_name).__doc__
    except ModuleNotFoundError:
        result = f'no help on topic {name!r}'
    return result


def main():
    """CLI entry point with clean interrupt handling."""
    try:
        _main()
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        raise SystemExit(130)
    except ConnectorError as error:
        print('gitdata: {}'.format(error), file=sys.stderr)
        raise SystemExit(1)


def _main():
    """Parse and dispatch a CLI command."""

    if len(sys.argv) == 1:
        print_help(__doc__)
        sys.exit()

    args = docopt(
        __doc__,
        version='gitdata version {}'.format(gitdata.__version__),
        options_first=True
    )

    if args['--debug']:
        print(_redact_debug_value(args))
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

    elif command == 'ls':
        from gitdata.cli.gitdata_ls import ls_to_console, __doc__ as doc
        args = docopt(doc, argv=argv)
        ls_to_console(args)

    elif command == 'scan':
        from gitdata.cli.gitdata_scan import scan_to_console, __doc__ as doc
        args = docopt(doc, argv=argv)
        scan_to_console(args)

    elif command in ('secret', 'secrets'):
        from gitdata.cli.gitdata_secrets import secrets, __doc__ as doc
        argv[0] = 'secret'
        args = docopt(doc, argv=argv)
        secrets(args)

    else:
        exit("%r is not a gitdata command. See 'gitdata help'." % args['<command>'])
