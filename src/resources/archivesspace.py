import odin

from aquarius import settings

from . import resource_configs

"""ArchivesSpace resources."""


class ArchivesSpaceRef(odin.Resource):
    """References to other objects."""
    ref = odin.StringField()


class ArchivesSpaceDate(odin.Resource):
    """Dates associated with a group of archival records."""
    expression = odin.StringField(null=True)
    begin = odin.StringField(null=True)
    end = odin.StringField(null=True)
    date_type = odin.StringField(choices=resource_configs.DATE_TYPE_CHOICES)
    label = odin.StringField(choices=resource_configs.DATE_LABEL_CHOICES)


class ArchivesSpaceExtent(odin.Resource):
    """The extent of a group of archival records."""
    number = odin.StringField()
    container_summary = odin.StringField(null=True)
    portion = odin.StringField(choices=(('whole', 'Whole'), ('part', 'Part')))
    extent_type = odin.StringField(
        choices=resource_configs.EXTENT_TYPE_CHOICES)


class ArchivesSpaceExternalId(odin.Resource):
    """An external identifier associated with a group of archival records."""
    external_id = odin.StringField()
    source = odin.StringField()


class ArchivesSpaceLinkedAgent(odin.Resource):
    """An agent linked to a group of archival records."""
    role = odin.StringField(
        choices=resource_configs.AGENT_ROLE_CHOICES, default="creator")
    relator = odin.StringField(
        choices=resource_configs.AGENT_RELATOR_CHOICES,
        null=True)
    ref = odin.StringField()


class ArchivesSpaceLanguageAndScript(odin.Resource):
    """Records the language and scripts of archival records.

    Applies to resources post-ArchivesSpace v2.7 only.
    """
    language = odin.StringField(null=True)


class ArchivesSpaceLangMaterial(odin.Resource):
    """Records information about the languages of archival records.

    Applies to resources post-ArchivesSpace v2.7 only.
    """
    language_and_script = odin.DictAs(ArchivesSpaceLanguageAndScript, null=True)


class ArchivesSpaceNameBase(odin.Resource):
    """Base class for names.

    Subclassed by names specific to an agent type."""
    rules = odin.StringField(default="dacs")
    source = odin.StringField(default="local")
    sort_name_auto_generate = odin.BooleanField(default=True)


class ArchivesSpaceNameCorporateEntity(ArchivesSpaceNameBase):
    """Names of organizations."""
    primary_name = odin.StringField()


class ArchivesSpaceNameFamily(ArchivesSpaceNameBase):
    """Names of families."""
    family_name = odin.StringField()


class ArchivesSpaceNamePerson(ArchivesSpaceNameBase):
    """Names of people."""
    primary_name = odin.StringField()
    rest_of_name = odin.StringField(null=True)
    name_order = odin.StringField(
        choices=(('direct', 'Direct'), ('inverted', 'Inverted')))


class ArchivesSpaceSubnote(odin.Resource):
    """A repeatable object containing note content."""
    jsonmodel_type = odin.StringField()
    publish = odin.BooleanField(default=False)
    content = odin.StringField(null=True)
    items = odin.StringField(null=True)


class ArchivesSpaceNote(odin.Resource):
    """A note describing a group of archival records."""
    publish = odin.BooleanField(default=False)
    jsonmodel_type = odin.StringField()
    type = odin.StringField()
    label = odin.StringField(null=True)
    subnotes = odin.ArrayOf(ArchivesSpaceSubnote, null=True)
    content = odin.StringField(null=True)
    items = odin.StringField(null=True)


class ArchivesSpaceRightsStatementAct(odin.Resource):
    """Documents permissions or restrictions associated with a group of
    archival records."""
    act_type = odin.StringField()
    start_date = odin.DateField()
    end_date = odin.DateField(null=True)
    restriction = odin.StringField()
    notes = odin.ArrayOf(ArchivesSpaceNote)


class ArchivesSpaceRightsStatement(odin.Resource):
    """A machine-actionable rights statement."""
    determination_date = odin.DateField(null=True)
    rights_type = odin.StringField()
    start_date = odin.DateField()
    end_date = odin.DateField(null=True)
    status = odin.StringField(null=True)
    other_rights_basis = odin.StringField(null=True)
    jurisdiction = odin.StringField(null=True)
    license_terms = odin.StringField(null=True)
    statute_citation = odin.StringField(null=True)
    notes = odin.ArrayOf(ArchivesSpaceNote)
    acts = odin.ArrayOf(ArchivesSpaceRightsStatementAct)


class ArchivesSpaceComponentBase(odin.Resource):
    """Base class for components, which describe groups of archival records."""
    class Meta:
        abstract = True

    COMPONENT_TYPES = (
        ('archival_object', 'Archival Object'),
        ('accession', 'Accession'),
    )

    dates = odin.ArrayOf(ArchivesSpaceDate)
    extents = odin.ArrayOf(ArchivesSpaceExtent)
    external_ids = odin.ArrayOf(ArchivesSpaceExternalId)
    instances = odin.ArrayField(null=True)
    jsonmodel_type = odin.StringField(choices=COMPONENT_TYPES)
    lang_materials = odin.ArrayOf(ArchivesSpaceLangMaterial, null=True)
    linked_agents = odin.ArrayOf(ArchivesSpaceLinkedAgent)
    notes = odin.ArrayOf(ArchivesSpaceNote)
    publish = odin.BooleanField(default=False)
    repository = odin.DictField(default={"ref": "/repositories/{}".format(settings.ARCHIVESSPACE['repo_id'])})
    rights_statements = odin.ArrayOf(ArchivesSpaceRightsStatement)
    title = odin.StringField(null=True)
    uri = odin.StringField()


class ArchivesSpaceArchivalObject(ArchivesSpaceComponentBase):
    """Groups of records that are part of collections."""
    language = odin.StringField(null=True)
    level = odin.StringField(choices=resource_configs.LEVEL_CHOICES)
    resource = odin.DictAs(ArchivesSpaceRef)
    parent = odin.DictField(null=True)


class ArchivesSpaceAccession(ArchivesSpaceComponentBase):
    """Groups of records as received from record creators."""
    accession_date = odin.StringField()
    access_restrictions_note = odin.StringField(null=True)
    acquisition_type = odin.StringField()
    content_description = odin.StringField()
    general_note = odin.StringField(null=True)
    id_0 = odin.StringField()
    id_1 = odin.StringField()
    related_resources = odin.ArrayOf(ArchivesSpaceRef)
    use_restrictions_note = odin.StringField(null=True)


class ArchivesSpaceAgentCorporateEntity(odin.Resource):
    """Organizations associated with groups of archival records."""
    agent_type = odin.StringField(default="agent_corporate_entity")
    names = odin.ArrayOf(ArchivesSpaceNameCorporateEntity)


class ArchivesSpaceAgentFamily(odin.Resource):
    """Families associated with groups of archival records."""
    agent_type = odin.StringField(default="agent_family")
    names = odin.ArrayOf(ArchivesSpaceNameFamily)


class ArchivesSpaceAgentPerson(odin.Resource):
    """People associated with groups of archival records."""
    agent_type = odin.StringField(default="agent_person")
    names = odin.ArrayOf(ArchivesSpaceNamePerson)


class ArchivesSpaceFileVersion(odin.Resource):
    """A file associated with a digital object."""
    file_uri = odin.StringField()
    use_statement = odin.StringField()


class ArchivesSpaceDigitalObject(odin.Resource):
    """A digital object representing a group of archival records."""
    jsonmodel_type = odin.StringField(default="digital_object")
    publish = odin.BooleanField(default=False)
    title = odin.StringField()
    digital_object_id = odin.IntegerField()
    file_versions = odin.ArrayOf(ArchivesSpaceFileVersion)
    repository = odin.DictField(default={"ref": "/repositories/{}".format(settings.ARCHIVESSPACE['repo_id'])})
