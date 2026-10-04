"""Shared process-global python-oracledb Thick-mode initialization."""

from threading import Lock


class OracleClientError(Exception):
    """Raised when Thick mode cannot be initialized."""


_MODE_LOCK = Lock()

_THIN_MODE_ERROR = (
    'Oracle Thick mode was requested, but this process has already started in '
    'Thin mode. Restart the process and use the +thick Oracle reference before '
    'any other Oracle connection.'
)

_CLIENT_ERROR = (
    'Oracle Thick mode requires Oracle Client libraries. Install Oracle Instant '
    'Client, ensure the operating system can load it, and retry.'
)


def _error_code(error):
    """Return a public python-oracledb error code without its details."""
    full_code = getattr(error, 'full_code', None)
    if full_code:
        return str(full_code)
    detail = error.args[0] if error.args else None
    full_code = getattr(detail, 'full_code', None)
    return str(full_code) if full_code else None


def _prepare_oracle_client(oracledb, thick):
    """Prepare the process mode while the caller holds ``_MODE_LOCK``."""
    if not thick or not oracledb.is_thin_mode():
        return
    try:
        oracledb.init_oracle_client()
    except oracledb.Error as error:
        if not oracledb.is_thin_mode():
            return
        if _error_code(error) == 'DPY-2019':
            raise OracleClientError(_THIN_MODE_ERROR) from None
        raise OracleClientError(_CLIENT_ERROR) from None


def prepare_oracle_client(oracledb, thick):
    """Initialize required Thick mode before the process opens a connection."""
    with _MODE_LOCK:
        _prepare_oracle_client(oracledb, thick)


def connect_oracle(oracledb, thick, *args, **kwargs):
    """Create a connection without racing process-global mode selection."""
    with _MODE_LOCK:
        _prepare_oracle_client(oracledb, thick)
        return oracledb.connect(*args, **kwargs)
