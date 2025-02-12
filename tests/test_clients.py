import json
import time
from datetime import date
from unittest import TestCase
from unittest.mock import patch

from asnake.client import ASnakeClient
from electronbonder.client import ElectronBond
from requests import Session
from requests.exceptions import HTTPError

from src.clients import (ArchivesSpaceClient, AuroraClient, AuroraClientError,
                         ZodiacClient, ZodiacClientError)

# TODO improve docstrings


class MockResponse(object):
    """Class used to mock HTTP responses"""

    def __init__(self, json_data, status_code, **kwargs):
        """Sets data, status code, and any other data passed in."""
        self.json_data = json_data
        self.status_code = status_code
        for k in kwargs:
            setattr(self, k, kwargs[k])

    def json(self):
        """Mocks the json method of an HTTP response"""
        return self.json_data

    def raise_for_status(self):
        """Mocks the raise_for_status method of HTTP responses"""
        raise HTTPError('Not found')


class ArchivesSpaceClientTests(TestCase):

    @patch('asnake.client.ASnakeClient.authorize')
    def setUp(self, mock_authorize):
        mock_authorize.return_value = True
        self.baseurl = "https://archivesspace.org"
        self.username = "admin"
        self.password = "password"
        self.repo_id = 2
        self.args = [self.baseurl, self.username, self.password, self.repo_id]
        self.client = ArchivesSpaceClient(*self.args)

    def test_init(self):
        self.assertEqual(self.client.repo_id, self.repo_id)
        self.assertIsInstance(self.client.client, ASnakeClient)
        self.assertEqual(
            self.client.TYPE_LIST,
            {'accession': ['accession', 'repositories/2/accessions'],
             'component': ['archival_object', 'repositories/2/archival_objects'],
             'digital object': ['digital_objects', 'repositories/2/digital_objects'],
             'family': ['agent_family', 'agents/families'],
             'organization': ['agent_corporate_entity', 'agents/corporate_entities'],
             'person': ['agent_person', 'agents/people']})

    @patch('asnake.client.ASnakeClient.get')
    @patch('asnake.client.ASnakeClient.post')
    def test_send_request(self, mock_post, mock_get):
        post_data = {"created": True}
        mock_post.return_value = MockResponse(post_data, 200)
        get_data = {"data": "foo"}
        mock_get.return_value = MockResponse(get_data, 200)

        output = self.client.send_request('get', '/repositories/2/resources/1')
        self.assertEqual(output, get_data)
        mock_get.assert_called_once_with('/repositories/2/resources/1', data='null')

        output = self.client.send_request('post', '/repositories/2/accessions', data={})
        self.assertEqual(output, post_data)
        mock_post.assert_called_once_with('/repositories/2/accessions', data=json.dumps({}))
        mock_post.reset_mock()

        mock_post.side_effect = [
            MockResponse({"error": {"id_0": "Field already exists"}}, 403),
            MockResponse(post_data, 200)]
        output = self.client.send_request('post', '/repositories/2/accessions', data={"id_1": "2"})
        self.assertEqual(output, post_data)
        self.assertEqual(mock_post.call_count, 2)
        mock_post.assert_any_call('/repositories/2/accessions', data=json.dumps({"id_1": "2"}))
        mock_post.assert_any_call('repositories/2/accessions', data=json.dumps({"id_1": "003"}))

    @patch('src.clients.ArchivesSpaceClient.send_request')
    def test_methods(self, mock_send_request):
        expected = {"foo": "bar"}
        data = {"baz": "buz"}
        url = "/repositories/2/accessions"
        mock_send_request.return_value = expected

        output = self.client.retrieve(url)
        self.assertEqual(output, expected)
        mock_send_request.assert_called_once_with('get', url)
        mock_send_request.reset_mock()

        output = self.client.create(data, 'accession')
        self.assertEqual(output, expected)
        mock_send_request.assert_called_once_with('post', 'repositories/2/accessions', {'baz': 'buz'})
        mock_send_request.reset_mock()

        output = self.client.update(url, data)
        self.assertEqual(output, expected)
        mock_send_request.assert_called_once_with('post', url, data)
        mock_send_request.reset_mock()

    @patch('asnake.client.ASnakeClient.get')
    @patch('src.clients.ArchivesSpaceClient.create')
    def test_get_or_create(self, mock_post, mock_get):
        expected_uri = "repositories/2/agents/people/1"
        data = {"foo": "bar"}
        mock_get.return_value.json.return_value = {"results": [{"uri": expected_uri}]}
        output = self.client.get_or_create('person', 'name', 'Mickey Mouse', time.time(), data)
        self.assertEqual(output, expected_uri)
        mock_get.assert_called_once_with(
            'repositories/2/search',
            params={
                'page': 1,
                'type[]': 'agent_person',
                'aq': '{"query": {"field": "name", "value": "Mickey Mouse", "jsonmodel_type": "field_query"}}'})
        mock_get.reset_mock()

        mock_get.return_value.json.side_effect = [
            {"results": []},
            [expected_uri],
            {"name": "Mickey Mouse", "uri": expected_uri}]
        output = self.client.get_or_create('person', 'name', 'Mickey Mouse', time.time(), data)
        self.assertEqual(output, expected_uri)
        self.assertEqual(mock_get.call_count, 3)
        mock_get.reset_mock()

        mock_get.return_value.json.side_effect = [
            {"results": []},
            ["repositories/2/agents/people/2"],
            {"name": "Minnie Mouse", "uri": "repositories/2/agents/people/1"}]
        mock_post.return_value = {"uri": expected_uri}
        output = self.client.get_or_create('person', 'name', 'Mickey Mouse', time.time(), data)
        self.assertEqual(output, expected_uri)
        self.assertEqual(mock_get.call_count, 3)
        mock_post.assert_called_once_with({'foo': 'bar'}, 'person')

    @patch('asnake.client.ASnakeClient.get')
    def test_next_accession_number(self, mock_get):
        current_year = str(date.today().year)
        mock_get.return_value = MockResponse({"total_hits": 1, "results": [{"identifier": f"{current_year}-001"}]}, 200)
        output = self.client.next_accession_number()
        self.assertEqual(output, f"{current_year}:002")

        mock_get.return_value = MockResponse({"total_hits": 1, "results": [{"identifier": "2020-010"}]}, 200)
        output = self.client.next_accession_number()
        self.assertEqual(output, f"{current_year}:001")


class AuroraClientTests(TestCase):

    # TODO add tests for strip_url and get

    @patch('electronbonder.client.ElectronBond.authorize_oauth')
    def setUp(self, mock_authorize):
        mock_authorize.return_value = True
        self.baseurl = "https://aurora.org"
        self.oauth_client_baseurl = "https://oauth.com"
        self.oauth_client_id = "123456789"
        self.oauth_client_secret = "abcdefg"
        self.args = {
            'baseurl': self.baseurl,
            'oauth_client_baseurl': self.oauth_client_baseurl,
            'oauth_client_id': self.oauth_client_id,
            'oauth_client_secret': self.oauth_client_secret
        }
        self.client = AuroraClient(**self.args)

    def test_init(self):
        """Asserts attributes are set correctly on class"""
        self.assertIsInstance(self.client.client, ElectronBond)
        self.assertEqual(self.client.client.config['baseurl'], self.baseurl)
        self.assertEqual(self.client.client.config['oauth_client_baseurl'], self.oauth_client_baseurl)
        self.assertEqual(self.client.client.config['oauth_client_id'], self.oauth_client_id)
        self.assertEqual(self.client.client.config['oauth_client_secret'], self.oauth_client_secret)

    @patch('electronbonder.client.ElectronBond.patch')
    def test_update(self, mock_patch):
        """Asserts URL construction and exception handling."""
        data = {"foo": "bar"}
        mock_patch.return_value = MockResponse(data, 200)

        output = self.client.update("https://example.org/accessions/1", data)
        self.assertEqual(output, data)
        mock_patch.assert_called_once_with(
            '/accessions/1/',
            data='{"foo": "bar"}',
            headers={'Content-Type': 'application/json'}
        )

        mock_patch.return_value = MockResponse({}, 404, text="Not Found")
        with self.assertRaises(AuroraClientError) as err:
            self.client.update("https://example.org/accessions/1", data)
        self.assertEqual(str(err.exception), "Error sending request /accessions/1/ to Aurora: 404 Not Found")


class ZodiacClientTests(TestCase):

    def setUp(self):
        self.args = ["https://zodiac.org/", "1a2b3c4d5e6f7h8i9j"]
        self.client = ZodiacClient(*self.args)

    def test_init(self):
        """Asserts attributes are set correctly"""
        self.assertIsInstance(self.client.session, Session)
        self.assertEqual(self.client.session.headers['Accept'], 'application/json')
        self.assertEqual(self.client.session.headers['X-Api-Key'], self.args[1])
        self.assertEqual(self.client.baseurl, self.args[0].rstrip('/'))

    @patch('src.clients.Session.get')
    def test_get(self, mock_get):
        """Asserts URL construction and exception handling"""
        data = {"foo": "bar"}
        mock_get.return_value.json.return_value = data

        output = self.client.get("/this/is/a/url")
        self.assertEqual(output, data)
        mock_get.assert_called_once_with("https://zodiac.org/this/is/a/url")

        mock_get.return_value = MockResponse({}, 404, text="Not found")
        with self.assertRaises(ZodiacClientError) as err:
            self.client.get("/this/is/a/url")
        self.assertEqual(str(err.exception), "Error fetching url https://zodiac.org/this/is/a/url: 404 Not found")
