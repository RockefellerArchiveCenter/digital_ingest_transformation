import json
from datetime import date

from asnake.client import ASnakeClient
from electronbonder.client import ElectronBond


class ArchivesSpaceClientError(Exception):
    pass


class UrsaMajorClientError(Exception):
    pass


class AuroraClientError(Exception):
    pass


class ArchivesSpaceClient(object):
    """Client to get and receive data from ArchivesSpace."""

    def __init__(self, baseurl, username, password, repo_id):
        self.client = ASnakeClient(baseurl=baseurl, username=username, password=password)
        self.repo_id = repo_id
        if not self.client.authorize():
            raise ArchivesSpaceClientError("Couldn't authenticate user credentials for ArchivesSpace")
        self.TYPE_LIST = {
            "family": ["agent_family", "agents/families"],
            "organization": ["agent_corporate_entity", "agents/corporate_entities"],
            "person": ["agent_person", "agents/people"],
            "component": ["archival_object", "repositories/{repo_id}/archival_objects".format(repo_id=self.repo_id)],
            "accession": ["accession", "repositories/{repo_id}/accessions".format(repo_id=self.repo_id)],
            "digital object": ["digital_objects", "repositories/{repo_id}/digital_objects".format(repo_id=self.repo_id)]
        }

    def send_request(self, method, url, data=None, **kwargs):
        """Base method for sending requests to ArchivesSpace."""
        r = getattr(self.client, method)(url, data=json.dumps(data), **kwargs)
        if r.status_code == 200:
            return r.json()
        else:
            if r.json()["error"].get("id_0"):
                """Account for indexing delays by bumping up to the next accession number."""
                id_1 = int(data["id_1"])
                id_1 += 1
                data["id_1"] = str(id_1).zfill(3)
                return self.create(data, "accession")
            raise ArchivesSpaceClientError("Error sending {} request to {}: {}".format(method, url, r.json()["error"]))

    def retrieve(self, url, **kwargs):
        return self.send_request("get", url, **kwargs)

    def create(self, data, type, **kwargs):
        return self.send_request("post", self.TYPE_LIST[type][1], data, **kwargs)

    def update(self, uri, data, **kwargs):
        return self.send_request("post", uri, data, **kwargs)

    def get_or_create(self, type, field, value, last_updated, consumer_data):
        """
        Attempts to find and return an object in ArchivesSpace.
        If the object is not found, creates and returns a new object.
        """
        model_type = self.TYPE_LIST[type][0]
        endpoint = self.TYPE_LIST[type][1]
        query = json.dumps({"query": {"field": field, "value": value, "jsonmodel_type": "field_query"}})
        try:
            r = self.client.get("repositories/{}/search".format(self.repo_id), params={"page": 1, "type[]": model_type, "aq": query}).json()
            if len(r["results"]) == 0:
                r = self.client.get(endpoint, params={"all_ids": True, "modified_since": last_updated - 120}).json()
                for ref in r:
                    r = self.client.get("{}/{}".format(endpoint, ref)).json()
                    if r[field] == str(value):
                        return r["uri"]
                return self.create(consumer_data, type).get("uri")
            return r["results"][0]["uri"]
        except Exception as e:
            raise ArchivesSpaceClientError("Error finding or creating object in ArchivesSpace: {}".format(e))

    def next_accession_number(self):
        """
        Finds the next available accession number by searching for accession
        numbers with the current year, and then incrementing.

        Assumes that accession numbers are in the format YYYY NNN, where YYYY
        is the current year and NNN is a zero-padded integer.
        """
        current_year = str(date.today().year)
        try:
            query = json.dumps({"query": {"field": "four_part_id", "value": current_year, "jsonmodel_type": "field_query"}})
            r = self.client.get("repositories/{}/search".format(self.repo_id), params={"page": 1, "type[]": "accession", "sort": "identifier desc", "aq": query}).json()
            number = "1"
            if r.get("total_hits") >= 1:
                if r["results"][0]["identifier"].split("-")[0] == current_year:
                    id_1 = int(r["results"][0]["identifier"].split("-")[1])
                    id_1 += 1
                    number = str(id_1).zfill(3)
            return ":".join([current_year, number.zfill(3)])
        except Exception as e:
            raise ArchivesSpaceClientError("Error retrieving next accession number from ArchivesSpace: {}".format(e))


class UrsaMajorClient(object):
    """Client to get and receive data from Ursa Major."""

    def __init__(self, baseurl):
        self.client = ElectronBond(baseurl=baseurl)

    def send_request(self, method, url, data=None, **kwargs):
        """Base class for sending requests to Ursa Major"""
        try:
            return getattr(self.client, method)(url, data=json.dumps(data), **kwargs).json()
        except Exception as e:
            raise UrsaMajorClientError("Error sending {} request to {}: {}".format(method, url, e))

    def retrieve(self, url, *args, **kwargs):
        return self.send_request("get", url, **kwargs)

    def update(self, url, data, **kwargs):
        return self.send_request("put", url, data, headers={"Content-Type": "application/json"}, **kwargs)

    def retrieve_paged(self, url, **kwargs):
        try:
            resp = self.client.get_paged(url, **kwargs)
            return resp
        except Exception as e:
            raise UrsaMajorClientError("Error retrieving list from Ursa Major: {}".format(e))

    def find_bag_by_id(self, identifier, **kwargs):
        """Finds a bag by its id."""
        try:
            bag_resp = self.client.get("bags/", params={"id": identifier}).json()
            count = bag_resp.get("count")
            if count != 1:
                raise UrsaMajorClientError("Found {} bags matching id {}, expected 1".format(count, identifier))
            bag_url = bag_resp.get("results")[0]["url"]
            return self.retrieve(bag_url)
        except Exception as e:
            raise UrsaMajorClientError("Error finding bag by id: {}".format(e))


class AuroraClient:
    """Client to update data in Aurora."""

    def __init__(self, baseurl, oauth_client_baseurl, oauth_client_id, oauth_client_secret):
        self.client = ElectronBond(
            baseurl=baseurl,
            oauth_client_baseurl=oauth_client_baseurl,
            oauth_client_id=oauth_client_id,
            oauth_client_secret=oauth_client_secret)
        if not self.client.authorize_oauth():
            raise AuroraClientError("Could not authorize Client ID {} in Aurora".format(oauth_client_id))

    def update(self, raw_url, data, **kwargs):
        """Sends a PATCH request.

        URL parsing strips the hostname off the URL so that the hostname
        configured for AuroraClient is always used."""
        identifier = raw_url.rstrip("/").split("/")[-1]
        prefix = raw_url.rstrip("/").split("/")[-2]
        url = "/{}/{}/".format(prefix.lstrip("/"), identifier.lstrip("/"))
        resp = self.client.patch(url, data=json.dumps(data), headers={"Content-Type": "application/json"}, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise AuroraClientError("Error sending request {} to Aurora: {}".format(url, resp.text))
