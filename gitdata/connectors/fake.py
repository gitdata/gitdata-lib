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

    def get(self, ref):
        if ref.startswith('fake'):
            return dict(
                people=self.people,
                addresses=self.addresses,
            )
