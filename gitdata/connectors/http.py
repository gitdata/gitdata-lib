"""
    http connector
"""

import io
import logging
import urllib
import urllib.parse

import requests

from gitdata.connectors.common import BaseConnector, Blob


logger = logging.getLogger(__name__)


def redact_url(ref):
    parts = urllib.parse.urlsplit(ref)
    if not parts.password:
        return ref
    host = parts.hostname or ''
    if parts.port:
        host = '{}:{}'.format(host, parts.port)
    if parts.username:
        netloc = '{}:***@{}'.format(parts.username, host)
    else:
        netloc = host
    return urllib.parse.urlunsplit(
        (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
    )


class HttpConnector(BaseConnector):

    def get(self, ref):
        """Get Data"""
        if ref.startswith('http://') or ref.startswith('https://'):
            safe_ref = redact_url(ref)
            logger.debug(
                '%s get %r',
                self.__class__.__name__,
                safe_ref
            )

            u = urllib.parse.urlparse(ref)
            endpoint = redact_url(urllib.parse.urldefrag(ref)[0])
            facts = dict(
                url=safe_ref,
                endpoint=endpoint,
                scheme=u.scheme,
                netloc=urllib.parse.urlsplit(safe_ref).netloc,
                username=u.username,
                hostname=u.hostname,
                port=u.port,
                path=u.path,
                lpath=str(endpoint).lower(),
                query=u.query,
                fragment=u.fragment,
                name=u.fragment or str(u.path).split('/')[-1],
            )

            r = requests.get(ref)
            if r.status_code == 200:
                return dict(
                    facts,
                    blob=Blob(r.content)
                )
            else:
                logger.error(
                    'status %s - %s get %r',
                    r.status_code,
                    self.__class__.__name__,
                    safe_ref
                )
