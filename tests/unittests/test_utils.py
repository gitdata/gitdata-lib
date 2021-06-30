"""
    test utils
"""

# pylint: disable=missing-docstring
# pylint: disable=invalid-name
# It's reasonable in this case.

import unittest

from gitdata import Record


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
