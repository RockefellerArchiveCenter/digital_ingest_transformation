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
                       SourcePackageToDigitalObject,
                       SourceRightsStatementToArchivesSpaceRightsStatement,
                       SourceTransferToTransferComponent, map_agents)
from .resources.source import (SourceAccession, SourceCreator, SourcePackage,
                               SourceRightsStatement, SourceTransfer)

logging.basicConfig(
    level=int(getenv('LOGGING_LEVEL', logging.INFO)),
    format='%(filename)s::%(funcName)s::%(lineno)s %(message)s')

# TODO convert data structure of identifiers to dict, rather than list of dicts
# TODO tidy up docstrings
# TODO implement logging
# TODO convert instances of "transfer" to "package"


class PackageTransformer(object):
    """Handles clients for interacting with external systems and defines the general structure of how routines process objects.
    Processes a single package object based on its structure and updates the package status.
    Transform object
        Overriden by each other class based on their routines
        Accession: Handles creation and linking of accesssions in AS
        Grouping: Manages grouping archival objects
        Transfer: Handles transfer objects and relationships to metadata
        Digital Object: Creates digital objects in AS and updates archival objects"""

    def __init__(self,
                 package_id,
                 zodiac_baseurl,
                 zodiac_api_key,
                 aurora_baseurl,
                 aurora_oauth_client_baseurl,
                 aurora_oauth_client_id,
                 aurora_oauth_client_secret,
                 as_baseurl,
                 as_username,
                 as_password,
                 as_repo_id):
        self.service_name = 'aquarius'
        self.package_id = package_id
        self.zodiac_client = ZodiacClient(zodiac_baseurl, zodiac_api_key)
        self.aspace_client = ArchivesSpaceClient(
            as_baseurl, as_username, as_password, as_repo_id)
        self.aurora_client = AuroraClient(
            aurora_baseurl,
            aurora_oauth_client_baseurl,
            aurora_oauth_client_id,
            aurora_oauth_client_secret)

    def run(self):
        try:
            package_data = self.zodiac_client.get(f'packages/{self.package_id}')
            if package_data.get('origin') == 'aurora':  # TODO should this be a helper method that can also be used below in update_archival_object?
                # TODO This is not actually a field on this object...yet
                aurora_accession_data = self.aurora_client.get(package_data['aurora_accession_identifier'])
                accession_created = self.create_accession(package_data, aurora_accession_data)
                group_created = self.create_archival_objects_group(accession_created, aurora_accession_data)
                transfer_created = self.create_archival_object_transfer(group_created)
                package_data = transfer_created
            do_created = self.create_digital_object(package_data)
            self.update_archival_object(do_created)
            self.update_aurora(do_created)
            self.deliver_success_notification(do_created)
        except Exception as err:
            self.deliver_failure_notification(err)

    def get_linked_agents(self, agents):
        """Transforms and creates ArchivesSpace agents.
        get_linked_agents: Creates and links agents in ArchivesSpace based on Aurora creator"""
        linked_agents = []
        for agent in agents:
            agent_data = map_agents(SourceCreator(type=agent["type"], name=agent["name"]))
            agent_ref = self.aspace_client.get_or_create(
                agent["type"], "title", agent["name"],
                int(time()), json.loads(json_codec.dumps(agent_data)))
            linked_agents.append({"uri": agent_ref})
        return linked_agents

    def create_accession(self, package_data, source_accession_data):
        """Link package information to archival accession data and ensures appropriate relationships are established. Creates Accessions.
            Get bag id from Ursa Major
            Set ursa major accession info to package accession info
            Check for first sibling
                if yes: set accession and resource and update ursa major accession info
                if no: use the ursa major client to retrieve data and set it. Use AS client to get next accession number. Gets and transforms AS data.
            Set aurora data based on retrieved information.
        """
        as_resource_uri = source_accession_data['resource']

        if source_accession_data.get('archivesspace_identifier'):
            as_accession_uri = source_accession_data['archivesspace_identifier']
        else:
            source_accession_data["accession_number"] = self.aspace_client.next_accession_number()
            source_accession_data["linked_agents"] = self.get_linked_agents(
                source_accession_data["creators"] + [{"name": source_accession_data["organization"], "type": "organization"}])
            source_accession_data["rights_statements"] = handle_open_dates(
                source_accession_data.get("rights_statements", []))
            transformed = get_transformed_object(source_accession_data, SourceAccession, SourceAccessionToArchivesSpaceAccession)
            as_accession_uri = self.aspace_client.create(transformed, "accession").get("uri")
            # TODO push AS accession data back to Aurora accession

        identifiers = {
            'aurora_accession': source_accession_data['url'],
            'aurora_transfer': package_data['url'],  # TODO should we pop this out of the package data?
            'archivesspace_accession': as_accession_uri,
            'archivesspace_resource': as_resource_uri
        }
        package_data.setdefault('identifiers', {}).update(identifiers)
        return package_data

    def create_archival_objects_group(self, package_data, accession_data):
        """Create a grouping component of related archival objects and organizes transfers into groups.
            Creates an archival object for the first package in an acesssion. Links other packages to this archival object.
            Check for a first sibling
                if yes: set the AS group URI to the first sibling's archivesspace group
                if no: use the ursa major client to get accession information and then use the AS client to make an archival object
            set the archivesspace group to the archivesspace group uri.
        """
        if accession_data.get("archivesspace_series_identifier"):  # TODO this field does not actually exist in Aurora right now. Needs to be added.
            as_group_uri = accession_data['archivesspace_series_identifier']
        else:
            accession_data["level"] = "recordgrp"
            accession_data["linked_agents"] = self.get_linked_agents(
                accession_data["creators"] + [{"name": accession_data["organization"], "type": "organization"}])
            accession_data["rights_statements"] = handle_open_dates(package_data.get("rights_statements", []))
            transformed = get_transformed_object(accession_data, SourceAccession, SourceAccessionToGroupingComponent)
            as_group_uri = self.aspace_client.create(transformed, "component").get("uri")

        package_data.setdefault('identifiers', {}).update({'archivesspace_group': as_group_uri})
        # TODO push group ID back to Aurora, or should this happen at the end?
        return package_data

    def create_archival_object_transfer(self, package_data):
        """Create a transfer level archival object which represents individual transfers and links them to existing groups.
            Creates an AS archival object for the first package in the transfer. Other packages in the transfer are linked to this AO
            Same as above, except for Transfer instead of Accession. Not exactly sure about the specifics of this.
        """
        if package_data.get('archivesspace_identifier'):
            as_transfer_uri = package_data['archivesspace_identifier']
        else:
            package_data["parent"] = package_data['identifiers']['archivesspace_group']
            package_data["resource"] = package_data['identifiers']['archivesspace_resource']
            package_data["level"] = "file"
            package_data["linked_agents"] = self.get_linked_agents(
                package_data["metadata"]["record_creators"] + [{"name": package_data["metadata"]["source_organization"], "type": "organization"}])
            package_data["rights_statements"] = handle_open_dates(package_data.get("rights_statements", []))
            transformed = get_transformed_object(package_data, SourceTransfer, SourceTransferToTransferComponent)
            as_transfer_uri = self.aspace_client.create(transformed, "component").get("uri")
        package_data.setdefault('identifiers', {}).update({'archivesspace_transfer': as_transfer_uri})
        # TODO update zodiac api
        return package_data

    def create_digital_object(self, package_data):
        """Make digital objects and updates associated archival objects.
            Creates an archival object and links it to an archival object
            Create a digital object for each package.
                Transform data based on mappings
                Get AS data and set title in the transformed data based on display string
                Check if digitized and set to publish if true
                Set do_uri based on AS digital object uri that is created by as client create using transformed data.
        """
        data = {"storage_uri": package_data['storage_uri'],
                "use_statement": package_data['use_statement']}  # TODO figure out what these attributes need to be. Does the webhook need to update package data?
        transformed = get_transformed_object(data, SourcePackage, SourcePackageToDigitalObject)
        transfer_component = self.aspace_client.retrieve(package_data['identifiers']['archivesspace_transfer'])  # TODO how do we get this for digitizd stuff?
        transformed['title'] = transfer_component['display_string']
        if package_data['origin'] == 'digitization':
            transformed['publish'] = True
        do_uri = self.aspace_client.create(transformed, "digital object").get("uri")

        self.update_archival_object(transfer_component, do_uri)

        # TODO check this - can we condense this?
        digital_objects = package_data.get('identifiers', {}).get('digital_objects', [])
        updated_digital_objects = digital_objects.append(do_uri)
        package_data.setdefault('identifiers', {}).update({'digital_objects': updated_digital_objects})  # TODO add Storage ID?
        return package_data

    def update_archival_object(self, package_data, transfer_component, do_uri):
        """Update the archival object with additional data about the digital object
            Check for rights statements and updates it based on the Aurora rights?
        """
        # TODO add comment about why this rights statement business is here.
        if not len(transfer_component.get("rights_statements")) and package_data['origin'] in ["digitization", "legacy_digital", "av_digitization"]:
            rights_data = package_data.get("rights_statements", [])
            transformed_rights = get_transformed_object(
                handle_open_dates(rights_data), SourceRightsStatement, SourceRightsStatementToArchivesSpaceRightsStatement)
            transfer_component["rights_statements"] = transformed_rights
        transfer_component["instances"].append(
            {"instance_type": "digital_object",
             "jsonmodel_type": "instance",
             "digital_object": {"ref": do_uri}})
        self.aspace_client.update(package_data['identifiers']['archivesspace_transfer'], transfer_component)

    def update_aurora(self, package_data):
        """Aurora Updates routine
            Send update requests for Aurora for different process statuses.
            Push transfer data updates to Aurora when digital objects are made.
            Send updates about archival accession data to Aurora.
        """
        self.aurora_client.update(package_data['url'], data=package_data)

    def deliver_success_notification(self, package_data):
        """Send SNS message about successful job.

        Args:
            package_path (pathlib.Path): location of the package binary
            data (dict): data about the package
        """
        client = get_client_with_role('sns', self.role_arn)  # TODO add this
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
            package_path (pathlib.Path): location of the package binary
            data (dict): data about the package
            exception (Exception): the exception that was thrown.
        """
        client = get_client_with_role('sns', self.role_arn)
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
    # TODO pass in variables from env
    PackageTransformer().run()
