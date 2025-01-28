# from .clients import ArchivesSpaceClient, UrsaMajorClient


class PackageTransformer():

    # def __init__(self):
    #    self.aspace_client = ArchivesSpaceClient(**settings.ARCHIVESSPACE)
    #    self.ursa_major_client = UrsaMajorClient(settings.URSA_MAJOR["baseurl"])

    def run(self):
        pass

    """Handles clients for interacting with external systems and defines the general structure of how routines process objects.
        Processes a single package object based on its structure and updates the package status.
        Transform object
            Overriden by each other class based on their routines
            Accession: Handles creation and linking of accesssions in AS
            Grouping: Manages grouping archival objects
            Transfer: Handles transfer objects and relationships to metadata
            Digital Object: Creates digital objects in AS and updates archival objects
        get_transformed_object: converts data based on predefined mapping
        get_linked_agents: Creates and links agents in ArchivesSpace based on Aurora creator
        first_sibling: Finds the first matching package object based on filters passed
        handle_open_dates: Converts open-ended dates into a structured (null) format

    Link package information to archival accession data and ensures appropriate relationships are established. Creates Accessions.
        Get bag id from Ursa Major
        Set ursa major accession info to package accession info
        Check for first sibling
            if yes: set accession and resource and update ursa major accession info
            if no: use the ursa major client to retrieve data and set it. Use AS client to get next accession number. Gets and transforms AS data.
        Set aurora data based on retrieved information.

    Create a grouping component of related archival objects and organizes transfers into groups.
        Creates an archival object for the first package in an acesssion. Links other packages to this archival object.
        Check for a first sibling
            if yes: set the AS group URI to the first sibling's archivesspace group
            if no: use the ursa major client to get accession information and then use the AS client to make an archival object
        set the archivesspace group to the archivesspace group uri

    Create a transfer level archival object which represents individual transfers and links them to existing groups.
        Creates an AS archival object for the first package in the transfer. Other packages in the transfer are linked to this AO
        Same as above, except for Transfer instead of Accession. Not exactly sure about the specifics of this.

    Make digital objects and updates associated archival objects.
        Creates an archival object and links it to an archival object
        Create a digital object for each package.
            Transform data based on mappings
            Get AS data and set title in the transformed data based on display string
            Check if digitized and set to publish if true
            Set do_uri based on AS digital object uri that is created by as client create using transformed data
        Update the archival object with additional data
            Check for rights statements and updates it based on the Aurora rights?

    Aurora Updates routine
        Send update requests for Aurora for different process statuses.
        Push transfer data updates to Aurora when digital objects are made.
        Send updates about archival accession data to Aurora.
    """


if __name__ == "__main__":
    PackageTransformer().run()
