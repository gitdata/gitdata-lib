"""
usage: gitdata secrets list [options]
       gitdata secrets ls [options]
       gitdata secrets get [options] <name>
       gitdata secrets set [options] <name> <value>
       gitdata secrets add [options] <name> <value>
       gitdata secrets delete [options] <name>
       gitdata secrets rm [options] <name>
       gitdata secrets keygen [options]

options:
    -h, --help
    -k --key=<val>       Encryption key
    --key-file=<path>    Read encryption key from file
"""

import sys

from gitdata.encryption import generate_key
from gitdata.repositories import Repository, locate_repository
from gitdata.secrets import SecretsKeyMissingException


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
