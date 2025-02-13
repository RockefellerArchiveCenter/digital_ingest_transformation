import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from src.helpers import handle_open_dates
from src.transform import PackageTransformer

FIXTURE_PATH = Path('tests', 'fixtures')


def json_from_fixture(fixture_name):
    """Returns JSON data from fixture files.

    Args:
        fixture_name (str): name of fixture to be loaded, relative to fixture dir.

    Returns:
        data (valid JSON): fixture data
    """
    with open(FIXTURE_PATH / fixture_name, 'r') as df:
        return json.load(df)


class TransformInitTests(TestCase):

    def setUp(self):
        self.args = ['package_id', 'sns_topic', 'sns_role', 'zodiac_baseurl', 'zodiac_api_key', 'aurora_baseurl', 'aurora_oauth_client_baseurl',
                     'aurora_oauth_client_id', 'aurora_oauth_client_secret', 30, 90, 'as_baseurl', 'as_username', 'as_password', 'as_repo_id']

    @patch('src.clients.ZodiacClient.__init__')
    @patch('src.clients.ArchivesSpaceClient.__init__')
    @patch('src.clients.AuroraClient.__init__')
    def test_init(self, mock_aurora, mock_as, mock_zodiac):
        """Asserts data attributes are set and clients instantiated as expected."""
        mock_aurora.return_value = None
        mock_as.return_value = None
        mock_zodiac.return_value = None

        transformer = PackageTransformer(*self.args)

        self.assertEqual(transformer.service_name, 'aquarius')
        self.assertEqual(transformer.package_id, self.args[0])
        mock_aurora.assert_called_once_with(self.args[5], self.args[6], self.args[7], self.args[8])
        mock_as.assert_called_once_with(self.args[11], self.args[12], self.args[13], self.args[14])
        mock_zodiac.assert_called_once_with(self.args[3], self.args[4])


class TransformMethodTest(TestCase):

    def setUp(self):
        self.package_id = "package_id"
        self.args = [self.package_id, 'sns_topic', 'sns_role', 'zodiac_baseurl', 'zodiac_api_key', 'aurora_baseurl', 'aurora_oauth_client_baseurl',
                     'aurora_oauth_client_id', 'aurora_oauth_client_secret', 30, 90, 'as_baseurl', 'as_username', 'as_password', 'as_repo_id']
        with patch('src.clients.ArchivesSpaceClient.__init__') as as_init:
            as_init.return_value = None
            with patch('src.clients.AuroraClient.__init__') as aurora_init:
                aurora_init.return_value = None
                self.transformer = PackageTransformer(*self.args)

    @patch('src.clients.ZodiacClient.get')
    @patch('src.clients.AuroraClient.get')
    @patch('src.transform.PackageTransformer.create_accession')
    @patch('src.transform.PackageTransformer.create_archival_objects_group')
    @patch('src.transform.PackageTransformer.create_archival_object')
    @patch('src.transform.PackageTransformer.create_digital_object')
    @patch('src.transform.PackageTransformer.update_archival_object')
    @patch('src.transform.PackageTransformer.update_aurora_package')
    @patch('src.transform.PackageTransformer.deliver_success_notification')
    @patch('src.transform.PackageTransformer.deliver_failure_notification')
    def test_run(self, mock_failure_message, mock_success_message, mock_update_aurora, mock_update_ao,
                 mock_do, mock_ao, mock_group, mock_accession, mock_accession_data, mock_package_data):
        """Asserts logic for digitization package."""
        accession_uri = "https://aurora.dev.rockarch.org/api/accessions/21"
        package_data = {
            "type": "package",
            "origin": "digitization",
            "aurora_accession_identifier": accession_uri}
        mock_package_data.return_value = package_data
        do_created = {"url": "foo", "created": "do"}
        mock_do.return_value = do_created

        self.transformer.run()

        mock_package_data.assert_called_once_with(f'packages/{self.transformer.package_id}')
        mock_do.assert_called_once_with(package_data)
        mock_update_ao.assert_called_once_with(do_created)
        mock_update_aurora.assert_called_once_with(do_created)
        mock_success_message.assert_called_once_with(do_created)

        for m in [mock_accession_data, mock_accession, mock_group, mock_ao, mock_failure_message]:
            m.assert_not_called()

        for m in [mock_do, mock_update_ao, mock_update_aurora, mock_success_message, mock_package_data]:
            m.reset_mock()

        """Asserts logic for Aurora package."""
        package_data["origin"] = "aurora"
        package_data["accession"] = accession_uri
        accession_data = {"type": "accession"}
        accession_created = {"created": "accession"}
        group_created = {"created": "group"}
        ao_created = {"created": "ao"}
        do_created = {"created": "do", "url": "foo"}
        mock_accession_data.return_value = accession_data
        mock_accession.return_value = accession_created
        mock_group.return_value = group_created
        mock_ao.return_value = ao_created
        mock_do.return_value = do_created

        self.transformer.run()

        mock_package_data.assert_called_once_with(f'packages/{self.transformer.package_id}')
        mock_do.assert_called_once_with(ao_created)
        mock_update_ao.assert_called_once_with(do_created)
        mock_update_aurora.assert_called_once_with(do_created)
        mock_success_message.assert_called_once_with(do_created)
        mock_accession_data.assert_called_once_with(accession_uri)
        mock_accession.assert_called_once_with(package_data, accession_data)
        mock_group.assert_called_once_with(accession_created, accession_data)
        mock_ao.assert_called_once_with(group_created)

        mock_failure_message.assert_not_called()

        """Asserts behavior when exception is thrown"""
        exception = Exception("foo")
        mock_package_data.side_effect = exception

        self.transformer.run()

        mock_failure_message.assert_called_once_with(exception)

    @patch('src.clients.AuroraClient.update')
    @patch('src.clients.ArchivesSpaceClient.next_accession_number')
    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_accession(self, mock_linked_agents, mock_create, mock_accession_number, mock_aurora_update):
        mock_accession_number.return_value = "2025:01"
        package_data = json_from_fixture('source/package.json')
        accession_data = json_from_fixture('source/accession.json')
        accession_exists = json_from_fixture('source/accession--accession_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')
        source_linked_agents = json_from_fixture('source/linked_agents.json')
        transformed_data = json_from_fixture('transformed/accession.json')
        returned_data = json_from_fixture('transformed/package--accession_created.json')
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/accessions/4172'}

        """Accession already exists."""
        output = self.transformer.create_accession(package_data, accession_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_accession_number, mock_create, mock_linked_agents, mock_aurora_update]:
            m.assert_not_called()

        """New data created."""
        output = self.transformer.create_accession(package_data, accession_data)
        self.assertEqual(output, returned_data)
        mock_accession_number.assert_called_once()
        mock_linked_agents.assert_called_once_with(source_linked_agents)
        mock_create.assert_called_once_with(transformed_data, "accession")
        mock_aurora_update.assert_called_once_with(accession_exists['url'], accession_exists)

    @patch('src.clients.AuroraClient.update')
    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_archival_objects_group(self, mock_linked_agents, mock_create, mock_update_aurora):
        package_data = json_from_fixture('source/package--accession_created.json')
        accession_data = json_from_fixture('source/accession--accession_exists.json')
        group_exists = json_from_fixture('source/accession--group_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')
        source_linked_agents = json_from_fixture('source/linked_agents.json')
        transformed_data = json_from_fixture('transformed/group.json')
        returned_data = json_from_fixture('transformed/package--group_created.json')
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/archival_objects/4753'}

        """Archival objects group already exists."""
        output = self.transformer.create_archival_objects_group(package_data, group_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_create, mock_linked_agents, mock_update_aurora]:
            m.assert_not_called()

        """New data created."""
        output = self.transformer.create_archival_objects_group(package_data, accession_data)
        self.assertEqual(output, returned_data)
        mock_linked_agents.assert_called_once_with(source_linked_agents)
        mock_create.assert_called_once_with(transformed_data, "component")
        mock_update_aurora.assert_called_once_with(group_exists['url'], group_exists)

    @patch('src.clients.AuroraClient.update')
    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_archival_object(self, mock_linked_agents, mock_create, mock_update_aurora):
        package_data = json_from_fixture('source/package--group_created.json')
        ao_exists = json_from_fixture('source/package--ao_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')
        source_linked_agents = json_from_fixture('source/linked_agents.json')
        transformed_data = json_from_fixture('transformed/archival_object.json')
        returned_data = json_from_fixture('transformed/package--ao_created.json')
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/archival_objects/2153'}

        """Archival object already exists."""
        output = self.transformer.create_archival_object(ao_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_create, mock_linked_agents, mock_update_aurora]:
            m.assert_not_called()

        """New data created."""
        output = self.transformer.create_archival_object(package_data)
        self.assertEqual(output, returned_data)
        mock_linked_agents.assert_called_once_with(source_linked_agents)
        mock_create.assert_called_once_with(transformed_data, "component")
        mock_update_aurora.assert_called_once_with(output['url'], output)

    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.clients.ArchivesSpaceClient.retrieve')
    @patch('src.transform.PackageTransformer.update_archival_object')
    def test_create_digital_object(self, mock_update_ao, mock_retrieve, mock_create):
        package_data = json_from_fixture('source/package--ao_created.json')
        package_data_digitization = json_from_fixture('source/package--ao_created--digitization.json')
        transformed_data = json_from_fixture('transformed/digital_object.json')
        transformed_data_digitization = json_from_fixture('transformed/digital_object--digitization.json')
        returned_data = json_from_fixture('transformed/package--do_created.json')
        returned_data_digitization = json_from_fixture('transformed/package--do_created--digitization.json')
        as_archival_object = json_from_fixture('source/as_archival_object.json')
        do_uri = "/repositories/2/digital_objects/3"
        mock_create.return_value = {"uri": do_uri}
        mock_retrieve.return_value = as_archival_object

        """Package originating in Aurora"""
        output = self.transformer.create_digital_object(package_data)
        self.assertEqual(output, returned_data)
        mock_retrieve.assert_called_once_with(package_data['identifiers']['archivesspace_archival_object'])
        mock_create.assert_called_once_with(transformed_data, 'digital object')
        mock_update_ao.assert_called_once_with(as_archival_object, do_uri)
        for m in [mock_retrieve, mock_create, mock_update_ao]:
            m.reset_mock()

        """Package originating in digitization"""
        output = self.transformer.create_digital_object(package_data_digitization)
        self.assertEqual(output, returned_data_digitization)
        mock_retrieve.assert_called_once_with(package_data['identifiers']['archivesspace_archival_object'])
        mock_create.assert_called_once_with(transformed_data_digitization, 'digital object')
        mock_update_ao.assert_called_once_with(as_archival_object, do_uri)

    @patch('src.clients.ArchivesSpaceClient.update')
    def test_update_archival_object(self, mock_update):
        package_data = json_from_fixture('source/package--do_created.json')
        package_data_digitization = json_from_fixture('source/package--do_created--digitization.json')
        as_component = json_from_fixture('source/as_archival_object.json')
        as_component_digitization = json_from_fixture('source/as_archival_object--digitization.json')
        transformed_as_archival_object = json_from_fixture('transformed/as_archival_object--with_do.json')
        transformed_as_archival_object_digitization = json_from_fixture('transformed/as_archival_object--with_do--digitization.json')
        do_uri = "/repositories/2/digital_objects/3"

        """Package originating in Aurora"""
        self.transformer.update_archival_object(package_data, as_component, do_uri)
        mock_update.assert_called_once_with(package_data['identifiers']['archivesspace_archival_object'], transformed_as_archival_object)
        mock_update.reset_mock()

        """Package originating in digitization"""
        self.transformer.update_archival_object(package_data_digitization, as_component_digitization, do_uri)
        mock_update.assert_called_once_with(package_data['identifiers']['archivesspace_archival_object'], transformed_as_archival_object_digitization)

    @patch('src.clients.AuroraClient.update')
    def test_update_aurora_package(self, mock_update):
        """Asserts attributes are set correctly."""
        package_url = "https://aurora.rockarch.org/api/transfers/1"
        initial_data = {"url": package_url, "identifiers": {"archivesspace_group": "bar"}}
        expected_data = initial_data.copy()
        expected_data['archivesspace_parent_identifier'] = 'bar'
        expected_data['process_status'] = 90

        self.transformer.update_aurora_package(initial_data)
        mock_update.assert_called_once_with(package_url, expected_data)

    @patch('src.clients.ArchivesSpaceClient.get_or_create')
    def test_get_linked_agents(self, mock_get_or_create):
        """Asserts transformation of linked agents."""
        source_agents = json_from_fixture('source/linked_agents.json')
        transformed_agents = json_from_fixture('transformed/linked_agents.json')
        as_agents = json_from_fixture('source/as_linked_agents.json')
        mock_get_or_create.side_effect = as_agents

        output = self.transformer.get_linked_agents(source_agents)
        self.assertEqual(output, transformed_agents)
        self.assertEqual(mock_get_or_create.call_count, len(source_agents))


class HelperTests(TestCase):

    def test_handle_open_dates(self):
        """Tests handle_open_dates helper."""
        input = json_from_fixture('source/rights_statements.json')
        expected = json_from_fixture('transformed/rights_statements.json')

        output = handle_open_dates(input)
        self.assertEqual(output, expected)
