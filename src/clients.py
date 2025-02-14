import json
from datetime import date

from asnake.client import ASnakeClient
from electronbonder.client import ElectronBond
from requests import Session
from requests.exceptions import HTTPError


class ArchivesSpaceClientError(Exception):
    pass


class AuroraClientError(Exception):
    pass


class ZodiacClientError(Exception):
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
            "component": ["archival_object", f"repositories/{self.repo_id}/archival_objects"],
            "accession": ["accession", f"repositories/{self.repo_id}/accessions"],
            "digital object": ["digital_objects", f"repositories/{self.repo_id}/digital_objects"]
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
        """Gets an object from ArchivesSpace, or creates a new one if it is not found.

        Uses two different search strategies to account for indexing delays.

        Args:
            type (str): Type of object to return
            field (str): Field present in the requested object
            value (str): Value of the field in the requested object
            last_updated (time.time): timestamp of current datetime
            consumer_data (dict): data used to create a new object if none exists

        Returns:
            str: URI of requested object
        """
        model_type = self.TYPE_LIST[type][0]
        endpoint = self.TYPE_LIST[type][1]
        modified_since_backoff = 360
        query = json.dumps({"query": {"field": field, "value": value, "jsonmodel_type": "field_query"}})
        try:
            r = self.client.get("repositories/{}/search".format(self.repo_id), params={"page": 1, "type[]": model_type, "aq": query}).json()
            if len(r["results"]) == 0:
                r = self.client.get(endpoint, params={"all_ids": True, "modified_since": last_updated - modified_since_backoff}).json()
                for ref in r:
                    r = self.client.get("{}/{}".format(endpoint, ref)).json()
                    if r[field] == str(value):
                        return r["uri"]
                return self.create(consumer_data, type).get("uri")
            return r["results"][0]["uri"]
        except Exception as e:
            raise ArchivesSpaceClientError("Error finding or creating object in ArchivesSpace: {}".format(e))

    def next_accession_number(self):
        """Finds the next available accession number.

        Searches for accession numbers with the current year, and then increments the latest by one.
        If no accessions are found in the current year, starts with the number 001.

        Assumes that accession numbers are in the format YYYY NNN, where YYYY
        is the current year and NNN is a zero-padded integer.
        """
        current_year = str(date.today().year)
        try:
            query = json.dumps({"query": {"field": "four_part_id", "value": current_year, "jsonmodel_type": "field_query"}})
            r = self.client.get("repositories/{}/search".format(self.repo_id), params={"page": 1,
                                "type[]": "accession", "sort": "identifier desc", "aq": query}).json()
            number = "1"
            if r.get("total_hits") >= 1:
                id_parts = r["results"][0]["identifier"].split("-")
                if id_parts[0] == current_year:
                    id_1 = int(id_parts[1])
                    id_1 += 1
                    number = str(id_1).zfill(3)
            return ":".join([current_year, number.zfill(3)])
        except Exception as e:
            raise ArchivesSpaceClientError("Error retrieving next accession number from ArchivesSpace: {}".format(e))


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

    def strip_url(self, raw_url):
        """Strips the hostname off the URL so that the configured hostname is used."""
        identifier = raw_url.rstrip("/").split("/")[-1]
        prefix = raw_url.rstrip("/").split("/")[-2]
        return f"/{prefix.lstrip('/')}/{identifier.lstrip('/')}/"

    def update(self, raw_url, data, **kwargs):
        """Sends an HTTP POST request."""
        url = self.strip_url(raw_url)
        resp = self.client.post(url, data=json.dumps(data), headers={"Content-Type": "application/json"}, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise AuroraClientError(f"Error sending request {url} to Aurora: {resp.status_code} {resp.text}")

    def get(self, raw_url, **kwargs):
        """Sends an HTTP GET request."""
        url = self.strip_url(raw_url)
        resp = self.client.get(url, headers={"Content-Type": "application/json"}, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise AuroraClientError(f"Error sending request {url} to Aurora: {resp.status_code} {resp.text}")


class ZodiacClient(object):

    def __init__(self, baseurl):
        self.session = Session()
        self.session.headers.update({
            'Accept': 'application/json',
        })
        self.baseurl = baseurl.rstrip('/')

    def get(self, uri):
        """Makes an HTTP GET request"""
        url = f'{self.baseurl}/{uri.lstrip("/")}'
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            return resp.json()
        except HTTPError:
            raise ZodiacClientError(f"Error fetching url {url}: {resp.status_code} {resp.text}")
