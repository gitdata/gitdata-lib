"""
    http connector
"""

import io
import logging
import urllib
import urllib.parse

import requests

from gitdata.connectors.common import BaseConnector


logger = logging.getLogger(__name__)


class HttpConnector(BaseConnector):

    def get(self, ref):
        """Get Data"""
        if ref.startswith('http://') or ref.startswith('https://'):
            logger.debug(
                '%s get %r',
                self.__class__.__name__,
                ref
            )

            u = urllib.parse.urlparse(ref)
            endpoint=urllib.parse.urldefrag(ref)[0]
            facts = dict(
                url=ref,
                endpoint=endpoint,
                scheme=u.scheme,
                netloc=u.netloc,
                username=u.username,
                password=u.password,
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
                    blob=io.BytesIO(r.content)
                )
            else:
                logger.error(
                    'status %s - %s get %r',
                    r.status_code,
                    self.__class__.__name__,
                    ref
                )
