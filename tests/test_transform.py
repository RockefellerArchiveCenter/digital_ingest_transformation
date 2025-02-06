from unittest import TestCase
from unittest.mock import patch

from src.transform import PackageTransformer


class TransformTests(TestCase):

    def setUp(self):
        self.package_id = "package_id"
        self.args = [self.package_id, 'zodiac_baseurl', 'zodiac_api_key', 'aurora_baseurl', 'aurora_oauth_client_baseurl',
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
        self.assertEqual(transformer.package_id, self.package_id)
        mock_aurora.assert_called_once_with(self.args[3], self.args[4], self.args[5], self.args[6])
        mock_as.assert_called_once_with(self.args[7], self.args[8], self.args[9], self.args[10])
        mock_zodiac.assert_called_once_with(self.args[1], self.args[2])

    def test_run(self):
        pass

    def test_create_accession(self):
        pass

    def create_archival_obects_group(self):
        pass

    def create_archival_object_transfer(self):
        pass

    def transform_digital_object(self):
        pass

    def update_archival_object(self):
        pass

    def update_aurora(self):
        pass

    def deliver_start_notification(self):
        pass

    def deliver_success_notification(self):
        pass

    def deliver_failure_notification(self):
        pass

    def get_transformed_object(self):
        pass

    def get_linked_agents(self):
        pass

    def first_sibling(self):
        pass

    def handle_open_dates(self):
        pass
