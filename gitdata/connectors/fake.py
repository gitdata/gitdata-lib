"""
    mock data
"""

import faker

from gitdata.connectors.common import BaseConnector


class FakeConnector(BaseConnector):

    @property
    def person(self):
        fake = faker.Faker()
        person = fake.profile()
        first_name, last_name = person['name'].split(maxsplit=1)
        return dict(
            first_name=first_name,
            last_name=last_name,
            birthdate=person['birthdate'],
            sex=person['sex']
        )

    @property
    def people(self):
        while True:
            yield self.person

    @property
    def address(self):
        fake = faker.Faker()
        return dict(
            street=fake.street_address(),
            city=fake.city(),
            state=fake.state(),
            postal_code=fake.postcode(),
        )

    @property
    def addresses(self):
        while True:
            yield self.address

    @property
    def location(self):
        fake = faker.Faker()
        lat, lng, name, country_code, timezone = fake.location_on_land()
        return dict(
            latitude=lat,
            longitude=lng,
            name=name,
            country_code=country_code,
            timezone=timezone,
        )

    @property
    def locations(self):
        while True:
            yield self.location

    def get(self, ref):
        if ref.startswith('fake'):
            print('ref is', ref)
            return dict(
                people=self.people,
                addresses=self.addresses,
                locations=self.locations,
            )
