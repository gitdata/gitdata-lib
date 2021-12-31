"""
    mock data
"""

import faker

from gitdata.connectors.common import BaseConnector


class FakeConnector(BaseConnector):

    @property
    def people(self):
        fake = faker.Faker()
        while True:
            person = fake.profile()
            first_name, last_name = person['name'].split(maxsplit=1)
            yield dict(
                first_name=first_name,
                last_name=last_name,
                birthdate=person['birthdate'],
                sex=person['sex']
            )

    @property
    def addresses(self):
        fake = faker.Faker()
        while True:
            yield dict(
                street=fake.street_address(),
                city=fake.city(),
                state=fake.state(),
                postal_code=fake.postcode(),
            )

    def get(self, ref):
        if ref.startswith('fake'):
            return dict(
                people=self.people,
                addresses=self.addresses,
            )
