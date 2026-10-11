
from django.test import TestCase
from rest_framework.test import APIClient


class SchemaTests(TestCase):

    def test_openapi_schema_lists_every_route(self):
        response = APIClient().get('/api/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        paths = set(response.json()['paths'])
        for expected in ('/api/health/', '/api/majors/grouped/', '/api/stats/general/',
                         '/api/stats/by-major/{major}/', '/api/articulation/colleges/',
                         '/api/articulation/{cc_code}/{uc_code}/{major_slug}/', '/api/transcript/upload/'):
            self.assertIn(expected, paths)
