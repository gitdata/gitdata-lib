"""
    GitLab Connector

    Exprimental!
"""

import logging
import requests

logger = logging.getLogger(__name__)


class GitLabConnector:

    def __init__(self, parameters):
        self.url = parameters['GITLAB_URL']
        self.token = parameters['GITLAB_PERSONAL_TOKEN']

    @staticmethod
    def index():
        return [
            'projects',
        ]

    def get(self, path, **kwargs):
        content = None
        query_args = dict(private_token=self.token)
        query_args.update(**kwargs)
        query = '&'.join('{}={}'.format(*item) for item in query_args.items())
        url = '{}/{}?{}'.format(self.url, path, query)
        response = requests.get(
            url,
            headers={
                'Accept': 'application/json',
            }
        )
        if response.status_code == 200:
            content = response.json()
        else:
            logger.error('Status: %s', response.status_code)
        return content

    @property
    def projects(self):

        page = 1
        projects = []
        page_of_projects = self.get('projects', per_page=100, statistics=True)
        if page_of_projects:
            while len(page_of_projects) and page < 10:
                projects.extend(page_of_projects)
                page += 1
                page_of_projects = self.get('projects', per_page=100, page=page, statistics=True)

        columns = [
            'id',
            'name',
            'path_with_namespace',
            'last_activity_at',
            'commits'
        ]

        return [columns] + projects
