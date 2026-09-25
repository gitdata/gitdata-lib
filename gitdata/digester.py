"""
    digester

    digests aribtrary data structures into facts
"""

import gitdata


def _leading_dots(predicate):
    return len(predicate) - len(predicate.lstrip('.'))


def value_predicate(predicate):
    """Escape a source predicate for use as a literal attribute."""
    leading_dots = _leading_dots(predicate)
    reserved_dots = 2 if predicate.lstrip('.') == 'includes' else 0
    return ('.' * (leading_dots + reserved_dots)) + predicate


def relationship_predicate(predicate):
    """Return the structural form of a source predicate."""
    return '.' + value_predicate(predicate)


def is_relationship(predicate):
    """Return whether a predicate denotes a node-to-node edge."""
    return _leading_dots(predicate) % 2 == 1


def is_collection_membership(predicate):
    """Return whether a predicate is reserved for collection membership."""
    return predicate in ('includes', '.includes')


def predicate_name(predicate):
    """Recover the source name from a value or relationship predicate."""
    leading_dots = _leading_dots(predicate)
    name = predicate[leading_dots:]
    if name == 'includes' and leading_dots >= 2:
        leading_dots -= 2
    return ('.' * (leading_dots // 2)) + name


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
                if isinstance(o, (dict, list, tuple, set)):
                    previous_count = len(known)
                    child = self._digest(known, o)
                    if len(known) > previous_count:
                        known.append((s, relationship_predicate(p), child))
                elif o is not None:
                    known.append((s, value_predicate(p), self._digest(known, o)))
            return s

        elif isinstance(data, (list, tuple, set)):
            s = self.new_uid()
            for item in data:
                if isinstance(item, (dict, list, tuple, set)):
                    previous_count = len(known)
                    child = self._digest(known, item)
                    if len(known) > previous_count:
                        known.append((s, '.includes', child))
                elif item is not None:
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
        """Undigest facts while preserving literal/reference distinctions."""
        subject_order = []
        referenced = set()

        for subject, predicate, value in facts:
            if subject not in data:
                subject_order.append(subject)
            relationship = is_relationship(predicate)
            name = predicate_name(predicate)
            if is_collection_membership(predicate):
                data.setdefault(subject, []).append((relationship, value))
            else:
                attributes = data.setdefault(subject, {})
                item = (relationship, value)
                if name not in attributes:
                    attributes[name] = item
                elif isinstance(attributes[name], list):
                    attributes[name].append(item)
                else:
                    attributes[name] = [attributes[name], item]
            if relationship:
                referenced.add(value)

        def resolve_value(tagged_value, resolving):
            relationship, value = tagged_value
            if relationship and value in data:
                return resolve_node(value, resolving)
            return value

        def resolve_node(subject, resolving):
            if subject in resolving:
                return subject
            resolving = resolving | {subject}
            value = data[subject]
            if isinstance(value, list):
                return [resolve_value(item, resolving) for item in value]
            return {
                name: (
                    [resolve_value(value, resolving) for value in item]
                    if isinstance(item, list)
                    else resolve_value(item, resolving)
                )
                for name, item in value.items()
            }

        roots = [subject for subject in subject_order if subject not in referenced]
        return {
            root: resolve_node(root, set())
            for root in roots
        }

    def undigest(self, facts):
        """undigest some facts"""
        data = {}
        result = self._undigest(facts, data)
        keys = list(result.keys())
        return result.pop(keys[0]) if keys else None


def digested(data, new_uid=gitdata.utils.new_uid):
    """Digest arbitrary data structure into facts"""
    digester = Digester(new_uid=new_uid)
    digester.digest(data)
    return digester.known


def undigested(facts):
    """Undigest facts into a data structure"""
    digester = Undigester()
    return digester.undigest(facts)
