import json
import logging
import traceback
from os import getenv
from time import time

from odin.codecs import json_codec

from .clients import ArchivesSpaceClient, AuroraClient, ZodiacClient
from .helpers import (get_client_with_role, get_transformed_object,
                      handle_open_dates)
from .mappings import (SourceAccessionToArchivesSpaceAccession,
                       SourceAccessionToGroupingComponent,
                       SourceArchivematicaPackageToDigitalObject,
                       SourcePackageToComponent,
                       SourceRightsStatementToArchivesSpaceRightsStatement,
                       map_agents)
from .resources.source import (SourceAccession, SourceArchivematicaPackage,
                               SourceCreator, SourcePackage,
                               SourceRightsStatement)

logging.basicConfig(
    level=int(getenv('LOGGING_LEVEL', logging.INFO)),
    format='%(filename)s::%(funcName)s::%(lineno)s %(message)s')


class PackageTransformer(object):
    """Transforms data associated with packages and saves it in external systems."""

    def __init__(self,
                 package_id,
                 sns_topic,
                 sns_role_arn,
                 zodiac_baseurl,
                 zodiac_api_key,
                 aurora_baseurl,
                 aurora_oauth_client_baseurl,
                 aurora_oauth_client_id,
                 aurora_oauth_client_secret,
                 aurora_accession_started_status,
                 aurora_package_complete_status,
                 as_baseurl,
                 as_username,
                 as_password,
                 as_repo_id):
        self.service_name = 'aquarius'
        self.package_id = package_id
        self.sns_topic = sns_topic
        self.sns_role_arn = sns_role_arn
        self.zodiac_client = ZodiacClient(zodiac_baseurl, zodiac_api_key)
        self.aspace_client = ArchivesSpaceClient(
            as_baseurl, as_username, as_password, as_repo_id)
        self.aurora_client = AuroraClient(
            aurora_baseurl,
            aurora_oauth_client_baseurl,
            aurora_oauth_client_id,
            aurora_oauth_client_secret)
        self.aurora_accession_started_status = aurora_accession_started_status
        self.aurora_package_complete_status = aurora_package_complete_status

    def run(self):
        """Main class method which calls all other methods."""
        try:
            package_data = self.zodiac_client.get(f'packages/{self.package_id}')
            if self.is_aurora_package(package_data):
                aurora_accession_data = self.aurora_client.get(package_data['aurora_accession_identifier'])
                accession_created = self.create_accession(package_data, aurora_accession_data)
                group_created = self.create_archival_objects_group(accession_created, aurora_accession_data)
                ao_created = self.create_archival_object(group_created)
                package_data = ao_created
            do_created = self.create_digital_object(package_data)
            self.update_archival_object(do_created)
            self.update_aurora_package(do_created)
            self.deliver_success_notification(do_created)
            logging.info(f'Data from package {self.package_id} transformed and saved.')
        except Exception as err:
            self.deliver_failure_notification(err)

    def is_aurora_package(self, package_data):
        """Checks if a package originates from Aurora.

        Args:
            package_data (dict): initial source package data from Zodiac.

        Returns:
            bool: indicates if package originated in Aurora.
        """
        return bool(package_data.get('origin') == 'aurora')

    def get_linked_agents(self, agents):
        """Transforms and creates ArchivesSpace agents.

        Args:
            agents (list of dicts): source data about agents.

        Returns:
            linked_agents (list of strs): ArchivesSpace URIs for agents.
        """
        linked_agents = []
        for agent in agents:
            agent_data = map_agents(SourceCreator(type=agent["type"], name=agent["name"]))
            agent_ref = self.aspace_client.get_or_create(
                agent["type"], "title", agent["name"],
                int(time()), json.loads(json_codec.dumps(agent_data)))
            linked_agents.append({"uri": agent_ref})
        logging.debug(f'Linked agents {agents} transformed to {linked_agents}')
        return linked_agents

    def create_accession(self, package_data, source_accession_data):
        """Creates accession in ArchivesSpace, if necessary.

        Args:
            package_data (dict): Source package data.
            source_accession_data (dict): Source accession data.

        Returns:
            package_data (dict): Updated package data
        """
        as_resource_uri = source_accession_data['resource']

        if source_accession_data.get('archivesspace_identifier'):
            as_accession_uri = source_accession_data['archivesspace_identifier']
        else:
            to_transform = source_accession_data.copy()
            to_transform["accession_number"] = self.aspace_client.next_accession_number()
            to_transform["linked_agents"] = self.get_linked_agents(
                to_transform["creators"] + [{"name": to_transform["organization"], "type": "organization"}])
            to_transform["rights_statements"] = handle_open_dates(
                to_transform.get("rights_statements", []))
            transformed = get_transformed_object(to_transform, SourceAccession, SourceAccessionToArchivesSpaceAccession)
            as_accession_uri = self.aspace_client.create(transformed, "accession").get("uri")
            source_accession_data['archivesspace_identifier'] = as_accession_uri
            source_accession_data['process_status'] = self.aurora_accession_started_status
            self.aurora_client.update(source_accession_data['url'], source_accession_data)

        identifiers = {
            'aurora_accession': source_accession_data['url'],
            # TODO this should be in the identifiers array already. If it is still in the `url` field it should be popped out of the package data?
            'aurora_package': package_data['url'],
            'archivesspace_accession': as_accession_uri,
            'archivesspace_resource': as_resource_uri
        }
        package_data.setdefault('identifiers', {}).update(identifiers)
        logging.debug(f'Accession {as_accession_uri} created for package {package_data["identifier"]}')
        return package_data

    def create_archival_objects_group(self, package_data, accession_data):
        """Create an ArchivesSpace grouping component (series) for archival objects, if necessary.

        Args:
            package_data (dict): Source package data.
            accession_data (dict): Source accession data.

        Returns:
            package_data (dict): Updated package data
        """
        if accession_data.get("archivesspace_group_identifier"):
            as_group_uri = accession_data['archivesspace_group_identifier']
        else:
            to_transform = accession_data.copy()
            to_transform["level"] = "recordgrp"
            to_transform["linked_agents"] = self.get_linked_agents(
                accession_data["creators"] + [{"name": accession_data["organization"], "type": "organization"}])
            to_transform["rights_statements"] = handle_open_dates(package_data.get("rights_statements", []))
            transformed = get_transformed_object(to_transform, SourceAccession, SourceAccessionToGroupingComponent)
            as_group_uri = self.aspace_client.create(transformed, "component").get("uri")
            accession_data['archivesspace_group_identifier'] = as_group_uri
            self.aurora_client.update(accession_data['url'], accession_data)

        package_data.setdefault('identifiers', {}).update({'archivesspace_group': as_group_uri})
        logging.debug(f'Grouping compnent {as_group_uri} created for package {package_data["identifier"]}')
        return package_data

    def create_archival_object(self, package_data):
        """Create an ArchivesSpace archival object for the package, if necessary.

        Args:
            package_data (dict): Source package data.

        Returns:
            package_data (dict): Updated package data
        """
        if package_data.get('archivesspace_identifier'):
            as_ao_uri = package_data['archivesspace_identifier']
        else:
            to_transform = package_data.copy()
            to_transform["parent"] = package_data['identifiers']['archivesspace_group']
            to_transform["resource"] = package_data['identifiers']['archivesspace_resource']
            to_transform["level"] = "file"
            to_transform["linked_agents"] = self.get_linked_agents(
                package_data["metadata"]["record_creators"] + [{"name": package_data["metadata"]["source_organization"], "type": "organization"}])
            to_transform["rights_statements"] = handle_open_dates(package_data.get("rights_statements", []))
            transformed = get_transformed_object(to_transform, SourcePackage, SourcePackageToComponent)
            as_ao_uri = self.aspace_client.create(transformed, "component").get("uri")
            package_data['archivesspace_identifier'] = as_ao_uri
            self.aurora_client.update(package_data['url'], package_data)
        package_data.setdefault('identifiers', {}).update({'archivesspace_archival_object': as_ao_uri})
        logging.debug(f'Archival object {as_ao_uri} created for package {package_data["identifier"]}')
        return package_data

    def create_digital_object(self, package_data):
        """Create an ArchivesSpace digital object for the package.

        Args:
            package_data (dict): Source package data.

        Returns:
            package_data (dict): Updated package data
        """
        data = {"storage_uri": package_data['storage_uri'],
                "use_statement": package_data['use_statement']}
        transformed = get_transformed_object(data, SourceArchivematicaPackage, SourceArchivematicaPackageToDigitalObject)
        archival_object = self.aspace_client.retrieve(
            package_data['identifiers']['archivesspace_archival_object'])
        transformed['title'] = archival_object['display_string']
        if package_data['origin'] == 'digitization':
            transformed['publish'] = True
        do_uri = self.aspace_client.create(transformed, "digital object").get("uri")

        self.update_archival_object(archival_object, do_uri)

        digital_objects = package_data.get('identifiers', {}).get('digital_objects', [])
        digital_objects.append(do_uri)
        package_data.setdefault('identifiers', {}).update({'digital_objects': digital_objects})  # TODO add Storage ID?
        logging.debug(f'Digital object {do_uri} created for package {package_data["identifier"]}')
        return package_data

    def update_archival_object(self, package_data, archival_object, do_uri):
        """Update the archival object with additional data about the digital object.

        Rights statements are added to packages which do not originate in Aurora
        and do not already have structured rights statements. This is because packages
        from those other sources have pre-existing archival objects in ArchivesSpace.

        Args:
            package_data (dict): Source package data.
            archival_object (dict): Archival object to be updated.
            do_uri (str): ArchivesSpace URI for digital object to add to instances.

        Returns:
            package_data (dict): Updated package data
        """
        if not len(archival_object.get("rights_statements")) and not self.is_aurora_package(package_data):
            rights_data = package_data.get("rights_statements", [])
            transformed_rights = get_transformed_object(
                handle_open_dates(rights_data), SourceRightsStatement, SourceRightsStatementToArchivesSpaceRightsStatement)
            archival_object["rights_statements"] = transformed_rights
        archival_object["instances"].append(
            {"instance_type": "digital_object",
             "jsonmodel_type": "instance",
             "digital_object": {"ref": do_uri}})
        self.aspace_client.update(package_data['identifiers']['archivesspace_archival_object'], archival_object)
        logging.debug(f'Archival object {package_data["identifiers"]["archivesspace_archival_object"]} updated for package {package_data["identifier"]}')

    def update_aurora_package(self, package_data):
        """Updates identifiers and process status and sends data to Aurora.

        Args:
            package_data (dict): updated package data
        """
        package_data['archivesspace_identifier'] = package_data['identifiers']['archivesspace_archival_object']
        package_data['archivesspace_parent_identifier'] = package_data['identifiers']['archivesspace_group']
        package_data['process_status'] = self.aurora_package_complete_status
        self.aurora_client.update(package_data['url'], package_data)

    def deliver_success_notification(self, package_data):
        """Send SNS message about successful job.

        Args:
            packaage_data (dict): data about the package
        """
        client = get_client_with_role('sns', self.sns_role_arn)
        client.publish(
            TopicArn=self.sns_topic,
            Message=f'Package {self.package_id} successfully discovered.',
            MessageAttributes={
                'package_id': {
                    'DataType': 'String',
                    'StringValue': self.package_id,
                },
                'service': {
                    'DataType': 'String',
                    'StringValue': self.service_name,
                },
                'outcome': {
                    'DataType': 'String',
                    'StringValue': 'SUCCESS',
                },
                'package_data': {
                    'DataType': 'String',
                    'StringValue': json.dumps(package_data),
                },
            })
        logging.debug('Success notification delivered.')

    def deliver_failure_notification(self, exception):
        """Send SNS message about failed job.

        Args:
            exception (Exception): the exception that was thrown.
        """
        client = get_client_with_role('sns', self.sns_role_arn)
        tb = ''.join(traceback.format_exception(exception)[:-1])
        client.publish(
            TopicArn=self.sns_topic,
            Message=f'Package {self.package_id} failed during discovery.',
            MessageAttributes={
                'package_id': {
                    'DataType': 'String',
                    'StringValue': self.package_id,
                },
                'service': {
                    'DataType': 'String',
                    'StringValue': self.service_name,
                },
                'outcome': {
                    'DataType': 'String',
                    'StringValue': 'FAILURE',
                },
                'message': {
                    'DataType': 'String',
                    'StringValue': str(exception),
                },
                'traceback': {
                    'DataType': 'String',
                    'StringValue': tb,
                }
            })
        logging.debug('Failure notification delivered.')


if __name__ == "__main__":
    package_id = getenv("PACKAGE_ID")
    sns_topic = getenv("AWS_SNS_TOPIC")
    sns_role_arn = getenv("AWS_SNS_ROLE_ARN")
    zodiac_baseurl = getenv("ZODIAC_BASEURL")
    zodiac_api_key = getenv("ZODIAC_API_KEY")
    aurora_baseurl = getenv("AURORA_BASEURL")
    aurora_oauth_client_baseurl = getenv("AURORA_OAUTH_CLIENT_BASEURL")
    aurora_oauth_client_id = getenv("AURORA_OAUTH_CLIENT_ID")
    aurora_oauth_client_secret = getenv("AURORA_OAUTH_CLIENT_SECRET")
    aurora_accession_started_status = int(getenv("AURORA_ACCESSION_STARTED_STATUS"))
    aurora_package_complete_status = int(getenv("AURORA_PACKAGE_COMPLETE_STATUS"))
    as_baseurl = getenv("AS_BASEURL")
    as_username = getenv("AS_USERNAME")
    as_password = getenv("AS_PASSWORD")
    as_repo_id = getenv("AS_REPO_ID")
    PackageTransformer(
        package_id,
        sns_topic,
        sns_role_arn,
        zodiac_baseurl,
        zodiac_api_key,
        aurora_baseurl,
        aurora_oauth_client_baseurl,
        aurora_oauth_client_id,
        aurora_oauth_client_secret,
        aurora_accession_started_status,
        aurora_package_complete_status,
        as_baseurl,
        as_username,
        as_password,
        as_repo_id
    ).run()
