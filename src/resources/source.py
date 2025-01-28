import odin


class SourceCreator(odin.Resource):
    CREATOR_TYPE_CHOICES = (
        ("person", "Person"),
        ("organization", "Organization"),
        ("family", "Family")
    )
    name = odin.StringField()
    type = odin.StringField(choices=CREATOR_TYPE_CHOICES)


class SourceLinkedCreator(odin.Resource):
    uri = odin.StringField()


class SourceRightsStatementAct(odin.Resource):
    act = odin.StringField()
    grant_restriction = odin.StringField()
    start_date = odin.DateField(null=True)
    end_date = odin.DateField(null=True)
    granted_note = odin.StringField(null=True)


class SourceRightsStatement(odin.Resource):
    rights_basis = odin.StringField()
    start_date = odin.DateField(null=True)
    end_date = odin.DateField(null=True)
    rights_granted = odin.ArrayOf(SourceRightsStatementAct)
    external_documents = odin.ArrayField(null=True)
    linked_agents = odin.ArrayField(null=True)
    basis_note = odin.StringField(null=True)
    copyright_status = odin.StringField(null=True)
    determination_date = odin.DateField(null=True)
    terms = odin.StringField(null=True)
    statute_citation = odin.StringField(null=True)
    other_basis = odin.StringField(null=True)
    jurisdiction = odin.StringField(null=True)


class SourceMetadata(odin.Resource):
    date_end = odin.DateField()
    date_start = odin.DateField()
    internal_sender_description = odin.StringField()
    language = odin.ArrayField()
    payload_oxum = odin.StringField()
    record_creators = odin.ArrayOf(SourceCreator)
    source_organization = odin.StringField()
    title = odin.StringField()


class SourceAccession(odin.Resource):
    title = odin.StringField()
    url = odin.StringField()
    extent_size = odin.IntegerField()
    extent_files = odin.IntegerField()
    start_date = odin.DateTimeField()
    end_date = odin.DateTimeField()
    organization = odin.StringField()
    rights_statements = odin.ArrayOf(SourceRightsStatement)
    creators = odin.ArrayOf(SourceCreator)
    resource = odin.StringField()
    accession_date = odin.StringField()
    access_restrictions = odin.StringField()
    use_restrictions = odin.StringField()
    acquisition_type = odin.StringField()
    description = odin.StringField()
    appraisal_note = odin.StringField(null=True)
    accession_number = odin.StringField(null=True)
    language = odin.StringField()
    linked_agents = odin.ArrayOf(SourceLinkedCreator, null=True)
    level = odin.StringField(null=True)


class SourceTransfer(odin.Resource):
    metadata = odin.DictAs(SourceMetadata)
    url = odin.StringField()
    rights_statements = odin.ArrayOf(SourceRightsStatement)
    resource = odin.StringField()
    parent = odin.StringField(null=True)
    linked_agents = odin.ArrayOf(SourceLinkedCreator, null=True)
    level = odin.StringField()


class SourcePackage(odin.Resource):
    storage_uri = odin.StringField()
    use_statement = odin.StringField()
