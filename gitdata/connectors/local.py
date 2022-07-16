"""
    local filesystem connector
"""

import datetime
import io
import os

from gitdata.connectors.common import BaseConnector

fromtimestamp = datetime.datetime.fromtimestamp

class FileConnector(BaseConnector):

    name = 'file'
    reads = ['location']
    writes = ['text', 'blob', 'stdout']

    # def connects(self, ref):
    #     return os.path.isfile(ref)

    def connect(self, ref):
        self.ref = ref
        return os.path.isfile(ref)

    def get_blobs(self):
        with open(self.ref, 'rb') as f:
            return [io.BytesIO(f.read())]

    def get(self, ref):
        if os.path.isfile(ref):
            stat = os.stat(ref)
            pathname = os.path.realpath(ref)
            path, filename = os.path.split(pathname)

            with open(ref, 'rb') as f:
                content = io.BytesIO(f.read())

            return dict(
                ref=ref,
                filename=filename,
                size=stat.st_size,
                modified=fromtimestamp(stat.st_mtime),
                created=fromtimestamp(stat.st_ctime),
                path=path,
                blob=content
            )

    def extract(self, ref):
        """extract data from a ref"""
        print('extracting', ref)
        if os.path.isfile(ref):
            stat = os.stat(ref)
            pathname = os.path.realpath(ref)
            path, filename = os.path.split(pathname)

            with open(ref, 'rb') as f:
                content = io.BytesIO(f.read())

            return dict(
                ref=ref,
                filename=filename,
                size=stat.st_size,
                modified=fromtimestamp(stat.st_mtime),
                created=fromtimestamp(stat.st_ctime),
                path=path,
                blob=content
            )


class DirectoryConnector(BaseConnector):

    name = 'directory'
    reads = ['location']
    writes = ['location']


#     def _views(self, target):
#         with open(target.pathname) as reader:
#             return [
#                 Source('blob', reader)
#             ]

#     def extract(self, source):
#         with open(source.patname) as reader:
#             return reader

#     # legacy
#     def collect(self, target):
#         with open(target.patname) as reader:
#             return reader

