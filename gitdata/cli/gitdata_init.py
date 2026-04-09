"""
usage: gitdata init [<path>]

options:
    -h, --help
"""

import gitdata.repositories


def init(args):
    """Initialize a gitdata repository."""
    path = args['<path>'] or '.'
    try:
        repository_path, created = gitdata.repositories.init_repository(path)
    except ValueError as error:
        raise SystemExit('fatal: {}'.format(error))

    if created:
        print('Initialized empty GitData repository in {}'.format(repository_path))
    else:
        print('GitData repository already initialized in {}'.format(repository_path))
