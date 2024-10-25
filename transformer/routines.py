import json
import time

from odin.codecs import json_codec

from aquarius import settings

from .clients import ArchivesSpaceClient, AuroraClient, UrsaMajorClient
from .mappings import (SourceAccessionToArchivesSpaceAccession,
                       SourceAccessionToGroupingComponent,
                       SourcePackageToDigitalObject,
                       SourceRightsStatementToArchivesSpaceRightsStatement,
                       SourceTransferToTransferComponent, map_agents)
from .models import Package
from .resources.source import (SourceAccession, SourceCreator, SourcePackage,
                               SourceRightsStatement, SourceTransfer)


class Routine:
    """Base routine class which is inherited by all other routines.

    Provides default clients for ArchivesSpace and Ursa Major, and instantiates
    a DataTransformer class.

    The `transform_object` method in the `run` function is intended to be
    overriden by routines which interact with specific types of objects.
    Requires the following variables to be overriden as well:
        start_status - the status of the objects to be acted on.
        end_status - the status to be applied to Package objects once the
                        routine has completed successfully.
        object_type - a string containing the object type of the routine.
    """

    def __init__(self):
        self.aspace_client = ArchivesSpaceClient(**settings.ARCHIVESSPACE)
        self.ursa_major_client = UrsaMajorClient(settings.URSA_MAJOR["baseurl"])
        self.start_time = int(time.time())

    def run(self):
        """Main method. Processes only one package at a time."""
        package = Package.objects.filter(process_status=self.start_status).first()
        if package:
            try:
                self.transform_object(package)
                package.process_status = self.end_status
                package.save()
                message = f"{self.object_type} created."
            except Exception as e:
                raise Exception(f"{self.object_type} error: {e}", package.bag_identifier)
        else:
            message = f"No {self.object_type.lower()}s to process."
        return (message, [package.bag_identifier] if package else None)

    def transform_object(self, package):
        raise NotImplementedError("You must implement a `transform_object` method")

    def get_transformed_object(self, data, from_resource, mapping):
        """Transforms data into the target object."""
        from_obj = json_codec.loads(json.dumps(data), resource=from_resource)
        return json.loads(json_codec.dumps(mapping.apply(from_obj)))

    def get_linked_agents(self, agents):
        """Transforms and creates ArchivesSpace agents."""
        linked_agents = []
        for agent in agents:
            agent_data = map_agents(SourceCreator(type=agent["type"], name=agent["name"]))
            agent_ref = self.aspace_client.get_or_create(
                agent["type"], "title", agent["name"],
                self.start_time, json.loads(json_codec.dumps(agent_data)))
            linked_agents.append({"uri": agent_ref})
        return linked_agents

    def first_sibling(self, filter_kwargs):
        """Returns the first Package object which matches filters passed, if it exists."""
        if Package.objects.filter(**filter_kwargs).exists():
            return Package.objects.filter(**filter_kwargs).first()
        return None

    def handle_open_dates(self, rights_statements):
        """Converts `open` dates to null dates"""
        for rights_statement in rights_statements:
            if str(rights_statement.get("end_date")).lower() == "open":
                rights_statement["end_date"] = None
            for granted in rights_statement.get("rights_granted"):
                if granted.get("end_date") == "open":
                    granted["end_date"] = None
        return rights_statements


class AccessionRoutine(Routine):
    """Creates an ArchivesSpace accession."""

    start_status = Package.SAVED
    end_status = Package.ACCESSION_CREATED
    object_type = "Accession"

    def transform_object(self, package):
        """Creates an accession for the first processed package in an accession.
        Other packages in the accession are linked to the existing accession
        information.
        """
        package_data = self.ursa_major_client.find_bag_by_id(package.bag_identifier)
        ursa_major_accession = package_data["accession"]
        first_sibling = self.first_sibling({"ursa_major_accession": ursa_major_accession})
        if first_sibling:
            archivesspace_accession_uri = first_sibling.archivesspace_accession
            archivesspace_resource_uri = first_sibling.archivesspace_resource
            aurora_accession = first_sibling.aurora_accession
        else:
            data = self.ursa_major_client.retrieve(ursa_major_accession).get("data")
            aurora_accession = data["url"]
            archivesspace_resource_uri = data["resource"]
            data["accession_number"] = self.aspace_client.next_accession_number()
            data["linked_agents"] = self.get_linked_agents(
                data["creators"] + [{"name": data["organization"], "type": "organization"}])
            data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
            transformed = self.get_transformed_object(data, SourceAccession, SourceAccessionToArchivesSpaceAccession)
            archivesspace_accession_uri = self.aspace_client.create(transformed, "accession").get("uri")
        package.aurora_accession = aurora_accession
        package.aurora_transfer = package_data["data"]["url"]
        package.archivesspace_accession = archivesspace_accession_uri
        package.archivesspace_resource = archivesspace_resource_uri
        package.ursa_major_accession = ursa_major_accession


class GroupingComponentRoutine(Routine):
    """Creates an ArchivesSpace archival object for a group of transfers."""

    start_status = Package.ACCESSION_UPDATE_SENT
    end_status = Package.GROUPING_COMPONENT_CREATED
    object_type = "Grouping component"

    def transform_object(self, package):
        """Creates an archival object for the first processed package in an
        accession. Other packages are linked to the existing archival object
        information.
        """
        first_sibling = self.first_sibling({
            "aurora_accession": package.aurora_accession,
            "archivesspace_group__isnull": False})
        if first_sibling:
            archivesspace_group_uri = first_sibling.archivesspace_group
        else:
            data = self.ursa_major_client.retrieve(package.ursa_major_accession).get("data")
            data["level"] = "recordgrp"
            data["linked_agents"] = self.get_linked_agents(
                data["creators"] + [{"name": data["organization"], "type": "organization"}])
            data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
            transformed = self.get_transformed_object(data, SourceAccession, SourceAccessionToGroupingComponent)
            archivesspace_group_uri = self.aspace_client.create(transformed, "component").get("uri")
        package.archivesspace_group = archivesspace_group_uri


class TransferComponentRoutine(Routine):
    """Creates an ArchivesSpace archival object for the transfer."""

    start_status = Package.GROUPING_COMPONENT_CREATED
    end_status = Package.TRANSFER_COMPONENT_CREATED
    object_type = "Transfer component"

    def transform_object(self, package):
        """Creates an archival object for the first package in a transfer. Other
        packages in the transfer are linked to existing archival object information.
        """
        first_sibling = self.first_sibling({
            "bag_identifier": package.bag_identifier,
            "archivesspace_transfer__isnull": False})
        if first_sibling:
            archivesspace_transfer_uri = first_sibling.archivesspace_transfer
        else:
            data = self.ursa_major_client.find_bag_by_id(package.bag_identifier).get("data")
            data["parent"] = package.archivesspace_group
            data["resource"] = package.archivesspace_resource
            data["level"] = "file"
            data["linked_agents"] = self.get_linked_agents(
                data["metadata"]["record_creators"] + [{"name": data["metadata"]["source_organization"], "type": "organization"}])
            data["rights_statements"] = self.handle_open_dates(data.get("rights_statements", []))
            transformed = self.get_transformed_object(data, SourceTransfer, SourceTransferToTransferComponent)
            archivesspace_transfer_uri = self.aspace_client.create(transformed, "component").get("uri")
        package.archivesspace_transfer = archivesspace_transfer_uri


class DigitalObjectRoutine(Routine):
    """Creates an ArchivesSpace digital object and links it to an archival object."""

    start_status = Package.TRANSFER_COMPONENT_CREATED
    end_status = Package.DIGITAL_OBJECT_CREATED
    object_type = "Digital object"

    def transform_object(self, package):
        """Creates a digital object for each package."""
        data = {"storage_uri": package.storage_uri, "use_statement": package.use_statement}
        transformed = self.get_transformed_object(data, SourcePackage, SourcePackageToDigitalObject)
        transfer_component = self.aspace_client.retrieve(package.archivesspace_transfer)
        transformed['title'] = transfer_component['display_string']
        if package.origin == 'digitization':
            transformed['publish'] = True
        do_uri = self.aspace_client.create(transformed, "digital object").get("uri")
        self.update_archival_object(package, do_uri)

    def update_archival_object(self, package, do_uri):
        """Adds additional data to the archival object to which the digital object is attached.

        If no rights statements are already assigned to the archival object, transforms
        and adds rights statements. Adds the newly created digital objects to the
        archival object's instances array.
        """
        transfer_component = self.aspace_client.retrieve(package.archivesspace_transfer)
        if not len(transfer_component.get("rights_statements")) and package.origin in ["digitization", "legacy_digital", "av_digitization"]:
            rights_data = self.ursa_major_client.find_bag_by_id(package.bag_identifier)["data"].get("rights_statements", [])
            transformed_rights = self.get_transformed_object(
                self.handle_open_dates(rights_data), SourceRightsStatement, SourceRightsStatementToArchivesSpaceRightsStatement)
            transfer_component["rights_statements"] = transformed_rights
        transfer_component["instances"].append(
            {"instance_type": "digital_object",
             "jsonmodel_type": "instance",
             "digital_object": {"ref": do_uri}})
        self.aspace_client.update(package.archivesspace_transfer, transfer_component)


class AuroraUpdater:
    """Base class for routines that interact with Aurora.

    Provides a web client and a `run` method.

    Subclasses inheriting this class should specify the following attributes:
        `start_status` - indicating the process_status for the beginning
                         queryset of objects.
        `end_status` - indicating the process_status that will be saved for all
                       objects in the initial queryset.
        `remote_url` - a string representing an attribute on a `Package` instance
                       which stores the URL to send the PATCH request to.
        `remote_process_status` - an integeter representation of the process
                                  status to send to the remote URL.
    """

    def __init__(self):
        self.client = AuroraClient(**settings.AURORA)

    def run(self):
        update_ids = []
        for package in Package.objects.filter(process_status=self.start_status, origin="aurora"):
            try:
                data = {"process_status": self.remote_process_status}
                self.client.update(getattr(package, self.remote_url), data=data)
                package.process_status = self.end_status
                package.save()
                update_ids.append(package.bag_identifier)
            except Exception as e:
                raise Exception(e)
        message = "Update requests sent." if len(update_ids) else "No update requests pending"
        return (message, update_ids)


class TransferUpdateRequester(AuroraUpdater):
    """Updates transfer data in Aurora."""
    start_status = Package.DIGITAL_OBJECT_CREATED
    end_status = Package.UPDATE_SENT
    remote_url = "aurora_transfer"
    remote_process_status = 90


class AccessionUpdateRequester(AuroraUpdater):
    """Updates accession data in Aurora."""
    start_status = Package.ACCESSION_CREATED
    end_status = Package.ACCESSION_UPDATE_SENT
    remote_url = "aurora_accession"
    remote_process_status = 30
