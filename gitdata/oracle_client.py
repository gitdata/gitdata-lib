"""Shared python-oracledb Thick-mode initialization."""

import os


class OracleClientError(Exception):
    """Raised when Thick mode cannot be initialized."""


_thick_ready = False

_THICK_ERROR = (
    'Oracle Thick mode requires Oracle Instant Client. Install Instant Client '
    'and retry, or set GITDATA_ORACLE_CLIENT_LIB_DIR to the client library '
    'directory.'
)


def reset_oracle_client_state():
    global _thick_ready
    _thick_ready = False


def prepare_oracle_client(oracledb, thick):
    global _thick_ready
    if not thick:
        return
    if _thick_ready:
        return
    kwargs = {}
    lib_dir = os.environ.get('GITDATA_ORACLE_CLIENT_LIB_DIR')
    if lib_dir:
        kwargs['lib_dir'] = lib_dir
    try:
        oracledb.init_oracle_client(**kwargs)
    except Exception:
        raise OracleClientError(_THICK_ERROR) from None
    _thick_ready = True
