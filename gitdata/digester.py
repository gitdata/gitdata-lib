"""
    digester

    digests aribtrary data structures into facts
"""

import gitdata


class Digester(object):
    """Digest arbitrary data structures into facts"""

    def __init__(self, data=None, new_uid=gitdata.utils.new_uid):
        self.known = []
        self.new_uid = new_uid
        if data:
            self.digest(data)

    def _digest(self, known, data):
        """digest some data"""

        if isinstance(data, dict):
            s = self.new_uid()
            for p, o in data.items():
                known.append((s, p, self._digest(known, o)))
            return s

        elif isinstance(data, (list, tuple, set)):
            s = self.new_uid()
            for item in data:
                known.append((s, 'includes', self._digest(known, item)))
            return s

        else:
            return data

    def digest(self, data):
        """digest some data"""
        known = []
        uid = self._digest(known, data)
        self.known = known
        return uid


class Undigester(object):
    """Convert facts into data structures"""

    def __init__(self, facts=None):
        self.objects = {}
        if facts:
            self.undigest(facts)

    def _undigest(self, facts, data):
        """undigest some facts"""

        for s, p, o in facts:
            if p == 'includes':
                data.setdefault(s, []).append(o)
            else:
                data.setdefault(s, {})[p] = o

        result = data.copy()

        for k, v in data.items():
            if isinstance(v, list):
                result[k] = [result.pop(i, i) for i in v]

        for k, v in result.items():
            if isinstance(v, dict):
                for p, o in v.items():
                    if o in result:
                        v[p] = result.get(o)

        return result

    def undigest(self, facts):
        """undigest some facts"""
        data = {}
        result = self._undigest(facts, data)
        return result.pop(list(result.keys())[0])


def digested(data, new_uid=gitdata.utils.new_uid):
    """Digest arbitrary data structure into facts"""
    digester = Digester(new_uid=new_uid)
    digester.digest(data)
    return digester.known


def undigested(facts):
    """Undigest facts into a data structure"""
    digester = Undigester()
    return digester.undigest(facts)
