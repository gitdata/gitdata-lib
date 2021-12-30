"""
    gitdata graph
"""

import base64
import datetime
from decimal import Decimal
from datetime import datetime, date

import gitdata
from gitdata.digester import digested, undigested
from gitdata.stores.facts import facts_of

def retype(value, value_type):
    """convert a value back to its original type"""
    if value_type == 'str':
        pass

    elif value_type == "int":
        value = int(value)

    elif value_type == 'float':
        value = float(value)

    elif value_type == 'decimal.Decimal':
        value = Decimal(value)

    elif value_type == "datetime.date":
        y = int(value[:4])
        m = int(value[5:7])
        d = int(value[8:10])
        value = date(y, m, d)

    elif value_type == "datetime":
        y = int(value[:4])
        m = int(value[5:7])
        d = int(value[8:10])
        hr = int(value[11:13])
        mn = int(value[14:16])
        sc = int(value[17:19])
        value = datetime(y, m, d, hr, mn, sc)

    elif value_type == "stream":
        value = None

    elif value_type == "datetime.datetime":
        y = int(value[:4])
        m = int(value[5:7])
        d = int(value[8:10])
        hr = int(value[11:13])
        mn = int(value[14:16])
        sc = int(value[17:19])
        value = datetime(y, m, d, hr, mn, sc)

    elif value_type == 'bool':
        value = (value == '1' or value == 'True')

    elif value_type == 'NoneType':
        value = None

    elif value_type == 'bytes':
        value = base64.b64decode(value)

    else:
        msg = 'unsupported data type: ' + repr(value_type)
        raise Exception(msg)

    return value


# class Node:
#     """Graph Node"""

#     graph = None
#     uid = None

#     def __init__(self, **kwargs):
#         self.__dict__.update(kwargs)

#     def add(self, relation, data):
#         """Add a related data to a node"""
#         uid = self.graph.add(data)
#         self.graph.store.add([(self.uid, relation, uid)])
#         return uid

#     def delete(self):
#         """Delete all facts related to a node"""
#         self.graph.store.remove(
#             self.graph.triples((self.uid, None, None))
#         )

#     def __getitem__(self, name):
#         values = self.graph.triples((self.uid, name, None))
#         return values[0][-1] if values else None

#     def __getattr__(self, name):
#         values = self.graph.triples((self.uid, name, None))
#         return values[0][-1] if values else None

#     def keys(self):
#         for k, _ in self.items():
#             yield k

#     def values(self):
#         for _, v in self.items():
#             yield v

#     def items(self):
#         for _, p, o in self.graph.triples((self.uid, None, None)):
#             if self.graph.get(o):
#                 o = Node(graph=self.graph, uid=o)
#             result = p, o
#             yield result

#     def __eq__(self, value):
#         return dict(self.items()) == dict(value)

#     def __iter__(self):
#         members = self.graph.query([
#             (self.uid, None, '_a'),
#             ('_a', 'includes', '?uid')
#         ])
#         if members:
#             for member in members:
#                 yield Node(graph=self.graph, **member)

#         if self.graph.triples((self.uid, 'includes', None)):
#             for _, _, o in self.graph.triples((self.uid, 'includes', None)):
#                 yield Node(graph=self.graph, uid=o)
#         return self.keys()

#     def __str__(self):

#         members = [o for s, p, o in self.graph.triples((self.uid, 'includes', None))]
#         if members:
#             return repr(tuple(Node(graph=self.graph, uid=n) for n in members))

#         name = '{}({})'.format(
#             self.__class__.__name__,
#             self.uid
#         )

#         t = ['  {} {}: {!r}'.format(
#             key,
#             '.'*(20-len(key[:20])),
#             value,
#         ) for key, value in self.items()]

#         return '\n'.join([name] + t)

#     def __repr__(self):
#         # pattern = (self.uid, None, None)
#         members = [o for s, p, o in self.graph.triples((self.uid, 'includes', None))]
#         if members:
#             return repr(tuple(Node(graph=self.graph, uid=n) for n in members))
#         return f'Node({self.uid})'


class Graph:
    """Basic Graph"""

    def __init__(self, location=None, new_uid=gitdata.utils.new_uid):
        self.facts = facts_of(location, new_uid=new_uid)
        self.new_uid = new_uid

    def setup(self):
        self.facts.setup()

    def add(self, data):
        """Add data to the graph"""
        return self.facts.add(digested(data, new_uid=self.new_uid))

    def clear(self):
        """Remove all facts from the graph"""
        self.facts.clear()

    def delete(self, pattern):
        """Delete all facts matching the pattern"""
        facts = self.facts.triples(pattern)
        self.facts.remove(facts)

    def get(self, uids):
        """Get a node of the graph"""

        as_list = True
        if not isinstance(uids, (list, tuple, set)):
            uids = [uids]
            as_list = False

        result = []
        for uid in sorted(uids):
            values = {k: v for _, k, v in self.facts.triples((uid, None, None))}
            if values:
                result.append(dict(**values))

        if result:
            if as_list:
                return result
            return result[0]

    def query(self, clauses):
        """Query the graph"""
        facts = self.facts
        bindings = None
        for clause in clauses:
            bpos = {}
            qc = []
            for pos, x in enumerate(clause):
                if isinstance(x, str) and (x.startswith('?') or x.startswith('_')):
                    qc.append(None)
                    bpos[x] = pos
                else:
                    qc.append(x)
            rows = list(facts.triples((qc[0], qc[1], qc[2])))
            # print(rows)
            if bindings is None:
                # This is the first pass, everything matches
                bindings = []
                for row in rows:
                    binding = {}
                    for var, pos in bpos.items():
                        binding[var] = row[pos]
                    bindings.append(binding)
            else:
                # in subsequent passes, eliminate bindings that dont work
                newb = []
                for binding in bindings:
                    for row in rows:
                        validmatch = True
                        tempbinding = binding.copy()
                        for var, pos in bpos.items():
                            if var in tempbinding:
                                if tempbinding[var] != row[pos]:
                                    validmatch = False
                            else:
                                tempbinding[var] = row[pos]
                        if validmatch:
                            newb.append(tempbinding)
                bindings = newb
        return [
            dict(
                (k[1:], v)
                for k, v in b.items()
                if k[0] == '?'
            ) for b in bindings
        ] if bindings else []

    def find(self, *args, **kwargs):
        """Find nodes"""
        query = []
        for i in args:
            query.append(('?subject', i, '?'+i))
        for k, v in kwargs.items():
            query.append(('?subject', k, v))
        subjects = set(record['subject'] for record in self.query(query))
        result = self.get(subjects) or []
        return result

    def first(self, *args, **kwargs):
        """Find first node"""
        result = self.find(*args, **kwargs)
        for record in result:
            return record

    def exists(self, *args, **kwargs):
        """Return True if specified nodes exist else return False"""
        return bool(self.first(*args, **kwargs))

    def __str__(self):
        """Human friendly string representation"""
        return '\n'.join(repr(triple) for triple in self.facts.triples())

    def __len__(self):
        return len(self.facts)
