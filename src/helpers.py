import json

import boto3
from aws_assume_role_lib import assume_role
from odin.codecs import json_codec


def get_client_with_role(resource, role_arn):
    """Gets Boto3 client which authenticates with a specific IAM role."""
    session = boto3.Session()
    assumed_role_session = assume_role(session, role_arn)
    return assumed_role_session.client(resource)


def get_transformed_object(data, from_resource, mapping):
    """Transforms data into the target object.
    get_transformed_object: converts data based on predefined mapping"""
    from_obj = json_codec.loads(json.dumps(data), resource=from_resource)
    return json.loads(json_codec.dumps(mapping.apply(from_obj)))


def handle_open_dates(rights_statements):
    """Converts `open` dates to null dates
    handle_open_dates: Converts open-ended dates into a structured (null) format"""
    for rights_statement in rights_statements:
        if str(rights_statement.get("end_date")).lower() == "open":
            rights_statement["end_date"] = None
        for granted in rights_statement.get("rights_granted"):
            if granted.get("end_date") == "open":
                granted["end_date"] = None
    return rights_statements
