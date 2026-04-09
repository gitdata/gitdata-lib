"""
usage: gitdata secret <command> [options] [<args>...]

Commands:
  add         Add a secret
  get         Retrieve a secret by name
  list,ls     List all secrets
  ls          List all secrets
  delete,rm   Delete a secret
  keygen      Generate a new secret key to stdout

Options:
  -v, --verbose  Enable verbose mode (for debugging purposes)
  -h, --help     Show this help message and exit
"""

import os
import sys
from secrets import token_hex

import gitdata.config
from gitdata.secrets import get_secrets

def get_key():
    key = gitdata.config.get('GITDATA_SECRET_ENCRYPTION_KEY')
    if not key:
        print('Encryption key missing')
        sys.exit(-1)
    return key

def secrets(args):

    if args:
        command = args['<args>'][0]
        if command == 'keygen':
            print(token_hex())

        elif command in ['list', 'ls']:
            secrets = get_secrets(get_key())
            t = secrets.list()
            if t:
                print('\n'.join(t))

        elif command in ['set', 'add']:
            secrets = get_secrets(get_key())
            if len(args['<args>']) != 3:
                print(__doc__)
            else:
                _, name, value = args['<args>']
                encrypted_value = secrets.set(name, value)
                print(f'{name}: {encrypted_value}')
                print('your secret is safe with me')

        elif command == 'get':
            secrets = get_secrets(get_key())
            if len(args['<args>']) != 2:
                print(__doc__)
            else:
                _, name = args['<args>']
                decrypted_value = secrets.get(name)
                print(f'{name}: {decrypted_value}')
                print('your secret was safe with me')

        elif command in ('delete', 'rm'):
            if len(args['<args>']) == 2:
                name = args['<args>'][1]
                secrets = get_secrets(get_key())
                try:
                    secrets.delete(name)
                except KeyError:
                    sys.exit(f'unknown secret {name!r}')
            else:
                print(__doc__)

        else:
            print('unknown command')
    else:
        print(__doc__)

    # print(f'Hello {key}!')
