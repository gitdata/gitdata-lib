"""
    test utils
"""

import unittest

from gitdata import Record
from gitdata.utils import RecordList


class TestRecord(unittest.TestCase):
    """Test the Record class"""

    def test_getitem_class_attribute(self):

        class Thing(Record):
            name = 'whatsit'

        thing = Thing()

        self.assertEqual(thing.name, 'whatsit')
        self.assertEqual(thing['name'], 'whatsit')

    def test_getitem_class_property(self):

        class Thing(Record):
            name = property(lambda a: 'whatsit')

        thing = Thing()

        self.assertEqual(thing.name, 'whatsit')
        self.assertEqual(thing['name'], 'whatsit')

    def test_getitem(self):

        car = Record(
            name='Car',
            model='Mini',
            brand='Austin',
            engine=Record(
                size=850,
                cylenders=4,
            )
        )

        self.assertEqual(car.engine.size, 850)

    def test_subrecord(self):

        class Car(Record):

            @property
            def cylender_size(self):
                return self.engine.size / self.engine.cylenders

            def start(self):
                return 'vrrooom'

        class Engine(Record):
            pass

        car = Car(
            name='Car',
            model='Mini',
            brand='Austin',
            engine=Engine(
                size=850,
                cylenders=4,
            )
        )

        self.assertEqual(car.name, 'Car')
        self.assertEqual(car.cylender_size, 212.5)
        self.assertEqual(car.start(), 'vrrooom')


class TestRecordlist(unittest.TestCase):

    def test_basic_formatting(self):
        records = RecordList([
            Record(name='Pat', age=25, address='1234 Smith St'),
            Record(name='Joe', age=125, address='1234 Wesson St'),
            Record(name='Sam', age=35, address='1234 Jones St'),
        ])
        self.assertEqual(
            str(records),
            """record
name age address
---- --- --------------
Pat   25 1234 Smith St
Joe  125 1234 Wesson St
Sam   35 1234 Jones St
3 record records"""
        )

    def test_empty(self):
        records = RecordList([])
        self.assertEqual(
            str(records),
            """Empty list"""
        )

    def test_hidden(self):
        class Special(Record):
            hidden = ['address']
        records = RecordList([
            Special(name='Pat', age=25, address='1234 Smith St'),
            Special(name='Joe', age=125, address='1234 Wesson St'),
            Special(name='Sam', age=35, address='1234 Jones St'),
        ])
        self.assertEqual(
            str(records),
            """special
name age
---- ---
Pat   25
Joe  125
Sam   35
3 special records"""
        )

    def test_empty_with_hidden(self):
        class Special(Record):
            hidden = ['address']
        records = RecordList([])
        self.assertEqual(
            str(records),
            """Empty list"""
        )
