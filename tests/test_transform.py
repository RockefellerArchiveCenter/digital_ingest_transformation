import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from src.helpers import handle_open_dates
from src.transform import PackageTransformer

# TODO docstrings

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
        self.args = ['package_id', 'zodiac_baseurl', 'zodiac_api_key', 'aurora_baseurl', 'aurora_oauth_client_baseurl',
                     'aurora_oauth_client_id', 'aurora_oauth_client_secret', 'as_baseurl', 'as_username', 'as_password', 'as_repo_id']

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
        mock_aurora.assert_called_once_with(self.args[3], self.args[4], self.args[5], self.args[6])
        mock_as.assert_called_once_with(self.args[7], self.args[8], self.args[9], self.args[10])
        mock_zodiac.assert_called_once_with(self.args[1], self.args[2])


class TransformMethodTest(TestCase):

    # TODO find better way of mocking data fixtures. They are getting overwritten

    def setUp(self):
        self.package_id = "package_id"
        self.args = [self.package_id, 'zodiac_baseurl', 'zodiac_api_key', 'aurora_baseurl', 'aurora_oauth_client_baseurl',
                     'aurora_oauth_client_id', 'aurora_oauth_client_secret', 'as_baseurl', 'as_username', 'as_password', 'as_repo_id']
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
    @patch('src.transform.PackageTransformer.update_aurora')
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

        # self.transformer.run()

        # mock_package_data.assert_called_once_with(f'packages/{self.transformer.package_id}')
        # for m in [mock_do, mock_update_ao, mock_update_aurora, mock_success_message]:
        #     m.assert_called_once()  # TODO assert args, will require setting up returns from other mocks
        #     m.reset_mock()

        # for m in [mock_accession_data, mock_accession, mock_group, mock_ao, mock_failure_message]:
        #     m.assert_not_called()

        # mock_package_data.reset_mock()

        """Asserts logic for aurora package."""
        package_data["origin"] = "aurora"
        package_data["accession"] = accession_uri
        accession_data = {"type": "accession"}
        accession_created = accession_data.update({"created": "accession"})
        group_created = accession_data.update({"created": "group"})
        ao_created = accession_data.update({"created": "ao"})
        do_created = accession_data.update({"created": "do"})
        mock_accession_data.return_value = accession_data
        mock_accession.return_value = accession_created
        mock_group.return_value = group_created
        mock_ao.return_value = ao_created
        mock_do.return_value = do_created

        self.transformer.run()

        mock_package_data.assert_called_once_with(f'packages/{self.transformer.package_id}')
        for m in [mock_do, mock_update_ao, mock_update_aurora, mock_success_message]:
            m.assert_called_once()  # TODO assert args, will require setting up returns from other mocks

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

    @patch('src.clients.ArchivesSpaceClient.next_accession_number')
    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_accession(self, mock_linked_agents, mock_create, mock_accession_number):
        mock_accession_number.return_value = "2025:01"
        package_data = json_from_fixture('source/package.json')
        accession_data = json_from_fixture('source/accession.json')
        accession_exists = json_from_fixture('source/accession--accession_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')  # TODO check this
        transformed_data = json_from_fixture('transformed/accession.json')
        returned_data = json_from_fixture('transformed/package--accession_created.json')
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/accessions/4172'}

        output = self.transformer.create_accession(package_data, accession_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_accession_number, mock_create, mock_linked_agents]:
            m.assert_not_called()

        package_data = json_from_fixture('source/package.json')  # TODO this is dumb
        output = self.transformer.create_accession(package_data, accession_data)
        self.assertEqual(output, returned_data)
        mock_accession_number.assert_called_once()
        mock_linked_agents.assert_called_once_with([  # TODO make this a fixture
            {'name': 'Custard Pie Appreciation Consortium', 'type': 'organization'},
            {'name': 'Desperate Dan Appreciation Society', 'type': 'organization'},
            {'name': 'Donor Organization', 'type': 'organization'}])
        mock_create.assert_called_once_with(transformed_data, "accession")

    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_archival_objects_group(self, mock_linked_agents, mock_create):
        package_data = json_from_fixture('source/package--accession_created.json')
        accession_data = json_from_fixture('source/accession.json')
        group_exists = json_from_fixture('source/accession--group_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')
        transformed_data = json_from_fixture('transformed/group.json')
        returned_data = json_from_fixture('transformed/package--group_created.json')
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/archival_objects/4753'}

        output = self.transformer.create_archival_objects_group(package_data, group_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_create, mock_linked_agents]:
            m.assert_not_called()

        package_data = json_from_fixture('source/package--accession_created.json')  # TODO this is dumb
        output = self.transformer.create_archival_objects_group(package_data, accession_data)
        self.assertEqual(output, returned_data)
        mock_linked_agents.assert_called_once_with([  # TODO make this a fixture
            {'name': 'Custard Pie Appreciation Consortium', 'type': 'organization'},
            {'name': 'Desperate Dan Appreciation Society', 'type': 'organization'},
            {'name': 'Donor Organization', 'type': 'organization'}])
        mock_create.assert_called_once_with(transformed_data, "component")

    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.transform.PackageTransformer.get_linked_agents')
    def test_create_archival_object(self, mock_linked_agents, mock_create):
        package_data = json_from_fixture('source/package--group_created.json')
        ao_exists = json_from_fixture('source/package--ao_exists.json')
        linked_agents = json_from_fixture('transformed/linked_agents.json')
        transformed_data = json_from_fixture('transformed/archival_object.json')
        returned_data = json_from_fixture('transformed/package--ao_created.json')
        returned_data_new_ao = json_from_fixture('transformed/package--ao_created--extra.json')  # TODO figure this out, this is BS
        mock_linked_agents.return_value = linked_agents
        mock_create.return_value = {'uri': '/repositories/2/archival_objects/2153'}

        output = self.transformer.create_archival_object(ao_exists)
        self.assertEqual(output, returned_data)
        for m in [mock_create, mock_linked_agents]:
            m.assert_not_called()

        output = self.transformer.create_archival_object(package_data)
        self.assertEqual(output, returned_data_new_ao)  # TODO we should not need a new fixture here
        mock_linked_agents.assert_called_once_with([  # TODO make this a fixture
            {'name': 'Custard Pie Appreciation Consortium', 'type': 'organization'},
            {'name': 'Desperate Dan Appreciation Society', 'type': 'organization'},
            {'name': 'Donor Organization', 'type': 'organization'}])
        mock_create.assert_called_once_with(transformed_data, "component")

    @patch('src.clients.ArchivesSpaceClient.create')
    @patch('src.clients.ArchivesSpaceClient.retrieve')
    @patch('src.transform.PackageTransformer.update_archival_object')
    def test_create_digital_object(self, mock_update_ao, mock_retrieve, mock_create):
        package_data = json_from_fixture('source/package--ao_created.json')
        # transformed_data = json_from_fixture('transformed/digital_object.json')
        returned_data = json_from_fixture('transformed/package--do_created.json')
        as_archival_object = json_from_fixture('source/as_archival_object.json')
        # updated_as_archival_object = json_from_fixture('source/as_archival_object--updated.json')
        do_uri = "/repositories/2/digital_objects/3"
        mock_create.return_value = {"uri": do_uri}
        mock_retrieve.return_value = as_archival_object

        output = self.transformer.create_digital_object(package_data)
        self.assertEqual(output, returned_data)
        mock_retrieve.assert_called_once_with(package_data['identifiers']['archivesspace_archival_object'])
        mock_create.assert_called_once_with(  # TODO why does this not work with a fixture?
            {'jsonmodel_type': 'digital_object', 'publish': False, 'title': 'American Foundation for the Blind - Drama', 'digital_object_id': '0a9c6171-a18d-4ff6-b9e7-bef01aaded10', 'file_versions': [{'file_uri': '/aips/0a9c6171-a18d-4ff6-b9e7-bef01aaded10', 'use_statement': 'master', '$': 'src.resources.archivesspace.ArchivesSpaceFileVersion'}], 'repository': {'ref': '/repositories/2'}, '$': 'src.resources.archivesspace.ArchivesSpaceDigitalObject'}, 'digital object')
        mock_update_ao.assert_called_once_with(as_archival_object, do_uri)

        # TODO digitization package

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
    def test_update_aurora(self, mock_update):
        package_data = json_from_fixture('source/package--do_created.json')
        self.transformer.update_aurora(package_data)

        mock_update.assert_called_once_with(package_data['url'], data=package_data)

    @patch('src.clients.ArchivesSpaceClient.get_or_create')
    def test_get_linked_agents(self, mock_get_or_create):
        source_agents = json_from_fixture('source/linked_agents.json')
        transformed_agents = json_from_fixture('transformed/linked_agents.json')
        as_agents = json_from_fixture('source/as_linked_agents.json')
        mock_get_or_create.side_effect = as_agents

        output = self.transformer.get_linked_agents(source_agents)
        self.assertEqual(output, transformed_agents)
        self.assertEqual(mock_get_or_create.call_count, len(source_agents))


class HelperTests(TestCase):

    def test_handle_open_dates(self):
        input = json_from_fixture('source/rights_statements.json')
        expected = json_from_fixture('transformed/rights_statements.json')

        output = handle_open_dates(input)
        self.assertEqual(output, expected)
