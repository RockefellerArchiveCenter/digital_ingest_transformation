import json
import logging
import traceback
from os import getenv
from time import time

import shortuuid
from amclient import AMClient, errors
from odin.codecs import json_codec

from src.clients import ArchivesSpaceClient, AuroraClient, ZodiacClient
from src.helpers import (get_client_with_role, get_transformed_object,
                         handle_open_dates)
from src.mappings import (SourceAccessionToArchivesSpaceAccession,
                          SourceAccessionToGroupingComponent,
                          SourceArchivematicaPackageToDigitalObject,
                          SourcePackageToComponent,
                          SourceRightsStatementToArchivesSpaceRightsStatement,
                          map_agents)
from src.resources.source import (SourceAccession, SourceCreator,
                                  SourceDigitalObject, SourcePackage,
                                  SourceRightsStatement)

logging.basicConfig(
    level=int(getenv('LOGGING_LEVEL', logging.INFO)),
    format='%(filename)s::%(funcName)s::%(lineno)s %(message)s')


class PackageTransformer(object):
    """Transforms data associated with packages and saves it in external systems."""

    def __init__(self,
                 environment,
                 package_id,
                 sns_topic,
                 sns_role_arn,
                 ssm_role_arn):
        self.service_name = 'digital_ingest_transformation'
        self.package_id = package_id
        self.sns_topic = sns_topic
        self.sns_role_arn = sns_role_arn
        self.ssm_role_arn = ssm_role_arn
        self.config = self.get_config(environment)
        self.archivematica_client = AMClient(
            ss_api_key=self.config['ARCHIVEMATICA_SS_API_KEY'],
            ss_user_name=self.config['ARCHIVEMATICA_SS_USER_NAME'],
            ss_url=self.config['ARCHIVEMATICA_SS_URL'])
        self.zodiac_client = ZodiacClient(self.config['ZODIAC_BASEURL'])
        self.aspace_client = ArchivesSpaceClient(
            self.config['AS_BASEURL'],
            self.config['AS_USERNAME'],
            self.config['AS_PASSWORD'],
            self.config['AS_REPO_ID'])
        self.aurora_client = AuroraClient(
            self.config['AURORA_BASEURL'],
            self.config['AURORA_OAUTH_CLIENT_BASEURL'],
            self.config['AURORA_OAUTH_CLIENT_ID'],
            self.config['AURORA_OAUTH_CLIENT_SECRET'])
        self.aurora_accession_started_status = self.config['AURORA_ACCESSION_STARTED_STATUS']
        self.aurora_package_complete_status = self.config['AURORA_PACKAGE_COMPLETE_STATUS']

    def run(self):
        """Main class method which calls all other methods."""
        try:
            self.deliver_start_notification()
            package_data = self.zodiac_client.get(f'packages/{self.package_id}')
            if self.is_aurora_package(package_data):
                aurora_package_data = self.aurora_client.get(package_data['identifiers']['aurora_package'])
                aurora_accession_data = self.aurora_client.get(package_data['aurora_accession_identifier'])
                accession_created = self.create_accession(aurora_package_data, aurora_accession_data)
                group_created = self.create_archival_objects_group(accession_created, aurora_accession_data)
                ao_created = self.create_archival_object(group_created)
                package_data = ao_created
            do_created = self.create_digital_object(package_data)
            self.update_archival_object(do_created)
            self.update_source_package(do_created)
            self.deliver_success_notification(do_created)
            logging.info(f'Data from package {self.package_id} transformed and saved.')
        except Exception as err:
            logging.error(err)
            self.deliver_failure_notification(err)

    def get_config(self, environment):
        """Fetch config values from Parameter Store.

        Args:
            ssm_parameter_path (str): Path to parameters

        Returns:
            configuration (dict): all parameters found at the supplied path.
        """
        ssm_parameter_path = f"/{environment}/{self.service_name}"
        configuration = {}
        ssm_client = get_client_with_role('ssm', self.ssm_role_arn)
        try:
            paginator = ssm_client.get_paginator('get_parameters_by_path')
            response_iterator = paginator.paginate(Path=ssm_parameter_path)
            for page in response_iterator:
                for entry in page['Parameters']:
                    param_path_array = entry.get('Name').split("/")
                    section_position = len(param_path_array) - 1
                    section_name = param_path_array[section_position]
                    configuration[section_name] = entry.get('Value')
        except BaseException:
            print("Encountered an error loading config from SSM.")
            traceback.print_exc()
        finally:
            return configuration

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
            accession_number = self.aspace_client.next_accession_number()
            to_transform["accession_number"] = accession_number
            to_transform["linked_agents"] = self.get_linked_agents(
                to_transform["creators"] + [{"name": to_transform["organization"], "type": "organization"}])
            to_transform["rights_statements"] = handle_open_dates(
                to_transform.get("rights_statements", []))
            transformed = get_transformed_object(to_transform, SourceAccession, SourceAccessionToArchivesSpaceAccession)
            as_accession_uri = self.aspace_client.create(transformed, "accession").get("uri")

            """Update accession data in Aurora."""
            source_accession_data['archivesspace_identifier'] = as_accession_uri
            source_accession_data['process_status'] = self.aurora_accession_started_status
            source_accession_data['accession_number'] = accession_number
            self.aurora_client.update(source_accession_data['url'], source_accession_data)

        identifiers = {
            'aurora_accession': source_accession_data['url'],
            'archivesspace_accession': as_accession_uri,
            'archivesspace_resource': as_resource_uri
        }
        package_data.setdefault('identifiers', {})
        package_data['identifiers'].update(identifiers)
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

            """Update accession data in Aurora"""
            accession_data['archivesspace_group_identifier'] = as_group_uri
            self.aurora_client.update(accession_data['url'], accession_data)

        package_data.setdefault('identifiers', {})
        package_data['identifiers'].update({'archivesspace_group': as_group_uri})
        logging.debug(f'Grouping component {as_group_uri} created for package {package_data["identifier"]}')
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

            """Update package data in Aurora."""
            package_data['archivesspace_identifier'] = as_ao_uri
            self.aurora_client.update(package_data['identifiers']['aurora_package'], package_data)

        package_data.setdefault('identifiers', {})
        package_data['identifiers'].update({'archivesspace_archival_object': as_ao_uri})
        logging.debug(f'Archival object {as_ao_uri} created for package {package_data["identifier"]}')
        return package_data

    def create_digital_object(self, package_data):
        """Create an ArchivesSpace digital object for the package.

        Args:
            package_data (dict): Source package data.

        Returns:
            package_data (dict): Updated package data
        """
        self.archivematica_client.package_uuid = package_data['identifiers']['archivematica_uuid']
        archivematica_data = self.archivematica_client.get_package_details()
        archival_object = self.aspace_client.retrieve(
            package_data['identifiers']['archivesspace_archival_object'])
        if isinstance(archivematica_data, int):
            raise Exception(errors.error_lookup(archivematica_data))

        data = {
            "identifier": package_data['identifier'],
            "title": archival_object['display_string'],
            "publish": True if package_data['origin'] == 'digitization' else False,
            "file_versions": [
                {
                    "file_uri": archivematica_data['resource_uri'],
                    "use_statement": 'aip'
                }
            ]
        }
        if package_data['origin'] == 'digitization':
            dimes_id = shortuuid.uuid(archival_object['uri'])
            data['file_versions'] += [
                {
                    "file_uri": f"{self.config['IIIF_MANIFEST_BASEURL'].rstrip('/')}/{dimes_id}",
                    "use_statement": 'iiif_manifest'
                },
                {
                    "file_uri": f"{self.config['DOWNLOAD_BASEURL'].rstrip('/')}/{dimes_id}",
                    "use_statement": 'download'
                }
            ]
        transformed = get_transformed_object(data, SourceDigitalObject, SourceArchivematicaPackageToDigitalObject)
        do_uri = self.aspace_client.create(transformed, "digital object").get("uri")

        """Update archival object in ArchivesSpace"""
        self.update_archival_object(archival_object, do_uri)

        digital_objects = package_data.get('identifiers', {}).get('archivesspace_digital_objects', [])
        digital_objects.append(do_uri)
        package_data.setdefault('identifiers', {})
        package_data['identifiers'].update({'archivesspace_digital_objects': digital_objects})
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

    def update_source_package(self, package_data):
        """Updates identifiers and process status and sends data to Aurora.

        The `archivesspace_archival_object` identifier has already been added in the `create_archival_object` method.

        Args:
            package_data (dict): updated package data
        """
        if self.is_aurora_package(package_data):
            package_data['archivesspace_parent_identifier'] = package_data['identifiers']['archivesspace_group']
            package_data['process_status'] = self.aurora_package_complete_status
            self.aurora_client.update(package_data['identifiers']['aurora_package'], package_data)
        self.zodiac_client.put(f'/packages/{self.package_id}', package_data)

    def deliver_start_notification(self):
        client = get_client_with_role('sns', self.sns_role_arn)
        client.publish(
            TopicArn=self.sns_topic,
            Message=f'Transformation for {self.package_id} started.',
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
                    'StringValue': 'STARTED',
                },
                'message': {
                    'DataType': 'String',
                    'StringValue': f'Transformation for {self.package_id} started.',
                }
            })
        logging.debug('Start notification delivered.')

    def deliver_success_notification(self, package_data):
        """Send SNS message about successful job.

        Args:
            packaage_data (dict): data about the package
        """
        client = get_client_with_role('sns', self.sns_role_arn)
        client.publish(
            TopicArn=self.sns_topic,
            Message=json.dumps(package_data),
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
                'message': {
                    'DataType': 'String',
                    'StringValue': f'Package {self.package_id} successfully discovered.',
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
            Message=tb,
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
                }
            })
        logging.debug('Failure notification delivered.')


if __name__ == "__main__":
    environment = getenv('ENV')
    package_id = getenv("PACKAGE_ID")
    sns_topic = getenv("AWS_SNS_TOPIC")
    sns_role_arn = getenv("AWS_SNS_ROLE_ARN")
    ssm_role_arn = getenv("AWS_SSM_ROLE_ARN")
    PackageTransformer(
        environment,
        package_id,
        sns_topic,
        sns_role_arn,
        ssm_role_arn,
    ).run()
