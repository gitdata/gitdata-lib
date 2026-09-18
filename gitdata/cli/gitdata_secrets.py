"""
usage: gitdata secret list [options]
       gitdata secret ls [options]
       gitdata secret get [options] <name>
       gitdata secret set [options] <name> <value>
       gitdata secret add [options] <name> <value>
       gitdata secret delete [options] <name>
       gitdata secret rm [options] <name>
       gitdata secret status [options] [<names>...]
       gitdata secret resolve [options] <names>...
       gitdata secret clear [options]
       gitdata secret keygen [options]

Share handoff: a shared .gitdata without the key cannot be read.
Recipients re-set values under the same names with their own key.

options:
    -h, --help
    -k --key=<val>       Encryption key
    --key-file=<path>    Read encryption key from file
    --prompt             Prompt to set missing secrets (CLI only)
    -f --force           Required to clear all secret values
"""

import getpass
import sys

from gitdata.encryption import generate_key
from gitdata.repositories import Repository, locate_repository
from gitdata.secrets import MissingSecrets, SecretsKeyMissingException


def _resolve_key(args):
    if args.get('--key-file'):
        try:
            with open(args['--key-file'], encoding='utf-8') as handle:
                return handle.read()
        except OSError as error:
            raise SystemExit('fatal: Error reading key file: {}'.format(error))
    return args.get('--key')


def _require_repository():
    path = locate_repository()
    if not path:
        raise SystemExit('fatal: not a gitdata repository')
    return Repository(path)


def _missing_exit(names):
    raise SystemExit('fatal: missing secrets: {}'.format(', '.join(names)))


def secrets(args):
    """Manage repository secrets."""

    if args['keygen']:
        print(generate_key().decode())
        return

    key = _resolve_key(args)
    repository = _require_repository()
    try:
        manager = repository.secrets(key=key)
    except SecretsKeyMissingException:
        raise SystemExit('fatal: Secrets encryption key missing')

    if args['list'] or args['ls']:
        for name in manager.keys():
            print(name)

    elif args['get']:
        name = args['<name>']
        value = manager.get(name)
        if value is None:
            raise SystemExit('fatal: secret not found: {}'.format(name))
        print(value)

    elif args['set'] or args['add']:
        name = args['<name>']
        value = args['<value>']
        if value == '-':
            value = sys.stdin.read().rstrip('\n')
        manager.set(name, value)
        print('secret set: {}'.format(name))

    elif args['delete'] or args['rm']:
        name = args['<name>']
        if not manager.exists(name):
            raise SystemExit('fatal: unknown secret {!r}'.format(name))
        manager.delete(name)
        print('secret deleted: {}'.format(name))

    elif args['status']:
        names = args.get('<names>') or []
        if names:
            for name in names:
                state = 'set' if manager.exists(name) else 'missing'
                print('{}\t{}'.format(name, state))
        else:
            keys = manager.keys()
            if not keys:
                print('secrets: none')
            else:
                print('secrets: {} set'.format(len(keys)))
                for name in keys:
                    print(name)

    elif args['resolve']:
        names = args['<names>']
        try:
            manager.resolve(names)
        except MissingSecrets as error:
            if not args.get('--prompt'):
                _missing_exit(error.names)
            for name in error.names:
                value = getpass.getpass('{}: '.format(name))
                if value:
                    manager.set(name, value)
            try:
                manager.resolve(names)
            except MissingSecrets as retry_error:
                _missing_exit(retry_error.names)

    elif args['clear']:
        if not args.get('--force'):
            raise SystemExit('fatal: use --force to clear all secret values')
        manager.clear()
        print('secrets cleared')
