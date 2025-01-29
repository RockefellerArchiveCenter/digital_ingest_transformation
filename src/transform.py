# from .clients import ArchivesSpaceClient, UrsaMajorClient

# from .mappings import (SourceAccessionToArchivesSpaceAccession,
#                       SourceAccessionToGroupingComponent,
#                       SourcePackageToDigitalObject,
#                       SourceRightsStatementToArchivesSpaceRightsStatement,
#                       SourceTransferToTransferComponent, map_agents)

# from .resources.source import (SourceAccession, SourceCreator, SourcePackage,
#                                SourceRightsStatement, SourceTransfer)


class PackageTransformer():
    """Handles clients for interacting with external systems and defines the general structure of how routines process objects.
    Processes a single package object based on its structure and updates the package status.
    Transform object
        Overriden by each other class based on their routines
        Accession: Handles creation and linking of accesssions in AS
        Grouping: Manages grouping archival objects
        Transfer: Handles transfer objects and relationships to metadata
        Digital Object: Creates digital objects in AS and updates archival objects"""

    # def __init__(self):
    #    self.aspace_client = ArchivesSpaceClient(**settings.ARCHIVESSPACE)
    #    self.ursa_major_client = UrsaMajorClient(settings.URSA_MAJOR["baseurl"])

    def run(self):
        self.create_accession()
        self.create_archival_obects_group()
        self.create_archival_object_transfer()
        self.transform_digital_object()
        self.update_archival_object()
        self.update_aurora()
        self.deliver_start_notification()
        self.deliver_success_notification()
        self.deliver_failure_notification()

    def get_transformed_object(self):
        """Transforms data into the target object.
        get_transformed_object: converts data based on predefined mapping"""
        # from_obj = json_codec.loads(json.dumps(data), resource=from_resource)
        # return json.loads(json_codec.dumps(mapping.apply(from_obj)))
    pass

    def get_linked_agents(self):
        """Transforms and creates ArchivesSpace agents.
        get_linked_agents: Creates and links agents in ArchivesSpace based on Aurora creator"""
        # linked_agents = []
        # for agent in agents:
        #     agent_data = map_agents(SourceCreator(type=agent["type"], name=agent["name"]))
        #     agent_ref = self.aspace_client.get_or_create(
        #         agent["type"], "title", agent["name"],
        #         self.start_time, json.loads(json_codec.dumps(agent_data)))
        #     linked_agents.append({"uri": agent_ref})
        # return linked_agents
        pass

    def first_sibling(self):
        """Returns the first Package object which matches filters passed, if it exists.
        first_sibling: Finds the first matching package object based on filters passed"""
        # if Package.objects.filter(**filter_kwargs).exists():
        #     return Package.objects.filter(**filter_kwargs).first()
        # return None
        pass

    def handle_open_dates(self):
        """Converts `open` dates to null dates
        handle_open_dates: Converts open-ended dates into a structured (null) format"""
        # for rights_statement in rights_statements:
        #     if str(rights_statement.get("end_date")).lower() == "open":
        #         rights_statement["end_date"] = None
        #     for granted in rights_statement.get("rights_granted"):
        #         if granted.get("end_date") == "open":
        #             granted["end_date"] = None
        # return rights_statements
        pass

    def create_accession(self):
        """Link package information to archival accession data and ensures appropriate relationships are established. Creates Accessions.
            Get bag id from Ursa Major
            Set ursa major accession info to package accession info
            Check for first sibling
                if yes: set accession and resource and update ursa major accession info
                if no: use the ursa major client to retrieve data and set it. Use AS client to get next accession number. Gets and transforms AS data.
            Set aurora data based on retrieved information.
        """
        # package_data = self.ursa_major_client.find_bag_by_id(package.bag_identifier)
        # ursa_major_accession = package_data["accession"]
        # first_sibling = self.first_sibling({"ursa_major_accession": ursa_major_accession})
        # if first_sibling:
        #     archivesspace_accession_uri = first_sibling.archivesspace_accession
        #     archivesspace_resource_uri = first_sibling.archivesspace_resource
        #     aurora_accession = first_sibling.aurora_accession
        # else:
        #     data = self.ursa_major_client.retrieve(ursa_major_accession).get("data")
        #     aurora_accession = data["url"]
        #     archivesspace_resource_uri = data["resource"]
        #     data["accession_number"] = self.aspace_client.next_accession_number()
        #     data["linked_agents"] = self.get_linked_agents(
        #         data["creators"] + [{"name": data["organization"], "type": "organization"}])
        #     data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
        #     transformed = self.get_transformed_object(data, SourceAccession, SourceAccessionToArchivesSpaceAccession)
        #     archivesspace_accession_uri = self.aspace_client.create(transformed, "accession").get("uri")
        # package.aurora_accession = aurora_accession
        # package.aurora_transfer = package_data["data"]["url"]
        # package.archivesspace_accession = archivesspace_accession_uri
        # package.archivesspace_resource = archivesspace_resource_uri
        # package.ursa_major_accession = ursa_major_accession
    pass

    def create_archival_obects_group(self):
        """Create a grouping component of related archival objects and organizes transfers into groups.
            Creates an archival object for the first package in an acesssion. Links other packages to this archival object.
            Check for a first sibling
                if yes: set the AS group URI to the first sibling's archivesspace group
                if no: use the ursa major client to get accession information and then use the AS client to make an archival object
            set the archivesspace group to the archivesspace group uri.
        """
        # first_sibling = self.first_sibling({
        #     "aurora_accession": package.aurora_accession,
        #     "archivesspace_group__isnull": False})
        # if first_sibling:
        #     archivesspace_group_uri = first_sibling.archivesspace_group
        # else:
        #     data = self.ursa_major_client.retrieve(package.ursa_major_accession).get("data")
        #     data["level"] = "recordgrp"
        #     data["linked_agents"] = self.get_linked_agents(
        #         data["creators"] + [{"name": data["organization"], "type": "organization"}])
        #     data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
        #     transformed = self.get_transformed_object(data, SourceAccession, SourceAccessionToGroupingComponent)
        #     archivesspace_group_uri = self.aspace_client.create(transformed, "component").get("uri")
        # package.archivesspace_group = archivesspace_group_uri
    pass

    def create_archival_object_transfer(self):
        """Create a transfer level archival object which represents individual transfers and links them to existing groups.
            Creates an AS archival object for the first package in the transfer. Other packages in the transfer are linked to this AO
            Same as above, except for Transfer instead of Accession. Not exactly sure about the specifics of this.
        """
        # first_sibling = self.first_sibling({
        #     "bag_identifier": package.bag_identifier,
        #     "archivesspace_transfer__isnull": False})
        # if first_sibling:
        #     archivesspace_transfer_uri = first_sibling.archivesspace_transfer
        # else:
        #     data = self.ursa_major_client.find_bag_by_id(package.bag_identifier).get("data")
        #     data["parent"] = package.archivesspace_group
        #     data["resource"] = package.archivesspace_resource
        #     data["level"] = "file"
        #     data["linked_agents"] = self.get_linked_agents(
        #         data["metadata"]["record_creators"] + [{"name": data["metadata"]["source_organization"], "type": "organization"}])
        #     data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
        #     transformed = self.get_transformed_object(data, SourceTransfer, SourceTransferToTransferComponent)
        #     archivesspace_transfer_uri = self.aspace_client.create(transformed, "component").get("uri")
        # package.archivesspace_transfer = archivesspace_transfer_uri
    pass

    def transform_digital_object(self):
        """Make digital objects and updates associated archival objects.
            Creates an archival object and links it to an archival object
            Create a digital object for each package.
                Transform data based on mappings
                Get AS data and set title in the transformed data based on display string
                Check if digitized and set to publish if true
                Set do_uri based on AS digital object uri that is created by as client create using transformed data.
        """
        # data = {"storage_uri": package.storage_uri, "use_statement": package.use_statement}
        # transformed = self.get_transformed_object(data, SourcePackage, SourcePackageToDigitalObject)
        # transfer_component = self.aspace_client.retrieve(package.archivesspace_transfer)
        # transformed['title'] = transfer_component['display_string']
        # if package.origin == 'digitization':
        #     transformed['publish'] = True
        # do_uri = self.aspace_client.create(transformed, "digital object").get("uri")
        # self.update_archival_object(package, do_uri)
    pass

    def update_archival_object(self):
        """Update the archival object with additional data about the digital object
            Check for rights statements and updates it based on the Aurora rights?
        """
        # transfer_component = self.aspace_client.retrieve(package.archivesspace_transfer)
        # if not len(transfer_component.get("rights_statements")) and package.origin in ["digitization", "legacy_digital", "av_digitization"]:
        #     rights_data = self.ursa_major_client.find_bag_by_id(package.bag_identifier)["data"].get("rights_statements", [])
        #     transformed_rights = self.get_transformed_object(
        #         self.handle_open_dates(rights_data), SourceRightsStatement, SourceRightsStatementToArchivesSpaceRightsStatement)
        #     transfer_component["rights_statements"] = transformed_rights
        # transfer_component["instances"].append(
        #     {"instance_type": "digital_object",
        #      "jsonmodel_type": "instance",
        #      "digital_object": {"ref": do_uri}})
        # self.aspace_client.update(package.archivesspace_transfer, transfer_component)
    pass

    def update_aurora(self):
        """Aurora Updates routine
            Send update requests for Aurora for different process statuses.
            Push transfer data updates to Aurora when digital objects are made.
            Send updates about archival accession data to Aurora.
        """
        # self.client = AuroraClient(**settings.AURORA)

        # update_ids = []
        # for package in Package.objects.filter(process_status=self.start_status, origin="aurora"):
        #     try:
        #         data = {"process_status": self.remote_process_status}
        #         self.client.update(getattr(package, self.remote_url), data=data)
        #         update_ids.append(package.bag_identifier)
        #     except Exception as e:
        #         raise Exception(e)
        # message = "Update requests sent." if len(update_ids) else "No update requests pending"
        # return (message, update_ids)
    pass

    def deliver_start_notification(self):
        """Send notification of service start"""
    #     client = get_client_with_role('sns', self.role_arn)
    #     client.publish(
    #         TopicArn=self.sns_topic,
    #         Message=f'Discovery for {self.package_id} started.',
    #         MessageAttributes={
    #             'package_id': {
    #                 'DataType': 'String',
    #                 'StringValue': self.package_id,
    #             },
    #             'service': {
    #                 'DataType': 'String',
    #                 'StringValue': self.service_name,
    #             },
    #             'outcome': {
    #                 'DataType': 'String',
    #                 'StringValue': 'STARTED',
    #             }
    #         })
    #     logging.debug('Start notification delivered.')
        pass

    def deliver_success_notification(self):
        """Send SNS message about successful job.

        Args:
            package_path (pathlib.Path): location of the package binary
            data (dict): data about the package
        """
        # client = get_client_with_role('sns', self.role_arn)
        # TODO evaluate what package data is and how stable that model is over time
        # package_data['package_path'] = package_path
        # client.publish(
        #     TopicArn=self.sns_topic,
        #     Message=f'Package {self.package_id} successfully discovered.',
        #     MessageAttributes={
        #         'package_id': {
        #             'DataType': 'String',
        #             'StringValue': self.package_id,
        #         },
        #         'service': {
        #             'DataType': 'String',
        #             'StringValue': self.service_name,
        #         },
        #         'outcome': {
        #             'DataType': 'String',
        #             'StringValue': 'SUCCESS',
        #         },
        #         'package_data': {
        #             'DataType': 'String',
        #             'StringValue': json.dumps(package_data),
        #         },
        #     })
        # logging.debug('Success notification delivered.')
        pass

    def deliver_failure_notification(self):
        """Send SNS message about failed job.

        Args:
            package_path (pathlib.Path): location of the package binary
            data (dict): data about the package
            exception (Exception): the exception that was thrown.
        """
        # client = get_client_with_role('sns', self.role_arn)
        # tb = ''.join(traceback.format_exception(exception)[:-1])
        # client.publish(
        #     TopicArn=self.sns_topic,
        #     Message=f'Package {self.package_id} failed during discovery.',
        #     MessageAttributes={
        #         'package_id': {
        #             'DataType': 'String',
        #             'StringValue': self.package_id,
        #         },
        #         'service': {
        #             'DataType': 'String',
        #             'StringValue': self.service_name,
        #         },
        #         'outcome': {
        #             'DataType': 'String',
        #             'StringValue': 'FAILURE',
        #         },
        #         'message': {
        #             'DataType': 'String',
        #             'StringValue': str(exception),
        #         },
        #         'traceback': {
        #             'DataType': 'String',
        #             'StringValue': tb,
        #         }
        #     })
        # logging.debug('Failure notification delivered.')
        pass


if __name__ == "__main__":
    PackageTransformer().run()
