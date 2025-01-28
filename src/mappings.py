import odin

from .resources.archivesspace import (ArchivesSpaceAccession,
                                      ArchivesSpaceAgentCorporateEntity,
                                      ArchivesSpaceAgentFamily,
                                      ArchivesSpaceAgentPerson,
                                      ArchivesSpaceArchivalObject,
                                      ArchivesSpaceDate,
                                      ArchivesSpaceDigitalObject,
                                      ArchivesSpaceExtent,
                                      ArchivesSpaceExternalId,
                                      ArchivesSpaceFileVersion,
                                      ArchivesSpaceLangMaterial,
                                      ArchivesSpaceLanguageAndScript,
                                      ArchivesSpaceLinkedAgent,
                                      ArchivesSpaceNameCorporateEntity,
                                      ArchivesSpaceNameFamily,
                                      ArchivesSpaceNamePerson,
                                      ArchivesSpaceNote, ArchivesSpaceRef,
                                      ArchivesSpaceRightsStatement,
                                      ArchivesSpaceRightsStatementAct,
                                      ArchivesSpaceSubnote)
from .resources.source import (SourceAccession, SourceCreator,
                               SourceLinkedCreator, SourcePackage,
                               SourceRightsStatement, SourceRightsStatementAct,
                               SourceTransfer)


def map_dates(date_start, date_end):
    if date_end > date_start:
        expression = '{} - {}'.format(
            date_start.strftime("%Y %B %e"),
            date_end.strftime("%Y %B %e"))
        return [ArchivesSpaceDate(
            expression=expression, begin=date_start, end=date_end,
            date_type="inclusive", label="creation")]
    else:
        expression = date_start.strftime("%Y %B %e")
        return [ArchivesSpaceDate(
            expression=expression, begin=date_start,
            date_type="single", label="creation")]


def map_extents(extent_size, extent_files):
    return [
        ArchivesSpaceExtent(number=str(extent_size), extent_type="bytes", portion="whole"),
        ArchivesSpaceExtent(number=str(extent_files), extent_type="files", portion="whole")
    ]


def map_language(lang):
    return ArchivesSpaceLangMaterial(
        language_and_script=ArchivesSpaceLanguageAndScript(
            language=lang))


def map_note_multipart(text, type):
    if len(text) > 0:
        return ArchivesSpaceNote(
            jsonmodel_type="note_multipart", type=type,
            subnotes=[ArchivesSpaceSubnote(content=text, jsonmodel_type="note_text")])


class SourceLinkedCreatorToArchivesSpaceLinkedAgent(odin.Mapping):
    from_obj = SourceLinkedCreator
    to_obj = ArchivesSpaceLinkedAgent

    mappings = (
        ("uri", None, "ref"),
    )


class SourceCreatorToArchivesSpaceAgentFamily(odin.Mapping):
    from_obj = SourceCreator
    to_obj = ArchivesSpaceAgentFamily

    @odin.map_field(from_field="name", to_field="names", to_list=True)
    def name(self, value):
        return [ArchivesSpaceNameFamily(family_name=value)]


class SourceCreatorToArchivesSpaceAgentPerson(odin.Mapping):
    from_obj = SourceCreator
    to_obj = ArchivesSpaceAgentPerson

    @odin.map_field(from_field="name", to_field="names", to_list=True)
    def name(self, value):
        if ', ' in value:
            name = value.rsplit(', ', 1)
        elif ' ' in value:
            name = value.rsplit(' ', 1)[::-1]
        else:
            name = [value, '']
        return [ArchivesSpaceNamePerson(
            primary_name=name[0], rest_of_name=name[1], name_order="inverted")]


class SourceCreatorToArchivesSpaceAgentCorporateEntity(odin.Mapping):
    from_obj = SourceCreator
    to_obj = ArchivesSpaceAgentCorporateEntity

    @odin.map_field(from_field="name", to_field="names", to_list=True)
    def name(self, value):
        return [ArchivesSpaceNameCorporateEntity(primary_name=value)]


def map_agents(agent):
    MAPPINGS = {
        "person": SourceCreatorToArchivesSpaceAgentPerson,
        "organization": SourceCreatorToArchivesSpaceAgentCorporateEntity,
        "family": SourceCreatorToArchivesSpaceAgentFamily,
    }
    return MAPPINGS[agent.type].apply(agent)


class SourceRightsStatementActToArchivesSpaceRightsStatementAct(odin.Mapping):
    from_obj = SourceRightsStatementAct
    to_obj = ArchivesSpaceRightsStatementAct

    mappings = (
        ("act", None, "act_type"),
        ("grant_restriction", None, "restriction"),
        ("start_date", None, "start_date"),
        ("end_date", None, "end_date"),
    )

    @odin.map_field(from_field="granted_note", to_field="notes", to_list=True)
    def notes(self, value):
        return [ArchivesSpaceNote(
            jsonmodel_type="note_rights_statement_act",
            type="additional_information", content=[value])] if value else []


class SourceRightsStatementToArchivesSpaceRightsStatement(odin.Mapping):
    from_obj = SourceRightsStatement
    to_obj = ArchivesSpaceRightsStatement

    mappings = (
        ("start_date", None, "start_date"),
        ("end_date", None, "end_date"),
        ("copyright_status", None, "status"),
        ("determination_date", None, "determination_date"),
        ("terms", None, "license_terms"),
        ("statute_citation", None, "statute_citation"),
    )

    @odin.map_field(from_field="other_basis", to_field="other_rights_basis")
    def other_rights_basis(self, value):
        return value.lower() if value else None

    @odin.map_field(from_field="rights_basis", to_field="rights_type")
    def rights_type(self, value):
        return value.lower() if value else None

    @odin.map_field(from_field="jurisdiction", to_field="jurisdiction")
    def jurisdiction(self, value):
        return value.upper() if value else None

    @odin.map_list_field(from_field="rights_granted", to_field="acts")
    def acts(self, value):
        return [SourceRightsStatementActToArchivesSpaceRightsStatementAct.apply(a) for a in value]

    @odin.map_field(from_field="basis_note", to_field="notes", to_list=True)
    def notes(self, value):
        return [ArchivesSpaceNote(
                jsonmodel_type="note_rights_statement",
                type="type_note", content=[value])]


class SourceAccessionToArchivesSpaceAccession(odin.Mapping):
    from_obj = SourceAccession
    to_obj = ArchivesSpaceAccession

    mappings = (
        ("description", None, "content_description"),
        ("acquisition_type", None, "acquisition_type"),
        ("use_restrictions", None, "use_restrictions_note"),
        ("access_restrictions", None, "access_restrictions_note"),
        ("accession_date", None, "accession_date"),
        ("title", None, "title")
    )

    @odin.map_field(from_field="url", to_field="external_ids", to_list=True)
    def url(self, value):
        return [ArchivesSpaceExternalId(external_id=value, source="aurora")]

    @odin.map_field(from_field=("extent_size", "extent_files"), to_field="extents", to_list=True)
    def extents(self, extent_size, extent_files):
        return map_extents(extent_size, extent_files)

    @odin.map_field(from_field="language", to_field="lang_materials", to_list=True)
    def lang_materials(self, value):
        return [map_language(value)]

    @odin.map_field(from_field=("start_date", "end_date"), to_field="dates", to_list=True)
    def dates(self, date_start, date_end):
        return map_dates(date_start, date_end)

    @odin.map_list_field(from_field="rights_statements", to_field="rights_statements", to_list=True)
    def rights_statements(self, value):
        return [SourceRightsStatementToArchivesSpaceRightsStatement.apply(v) for v in value]

    @odin.map_field(from_field="resource", to_field="related_resources", to_list=True)
    def resource(self, value):
        return [ArchivesSpaceRef(ref=value)]

    @odin.map_field(from_field="accession_number", to_field=("id_0", "id_1"))
    def accession_number(self, accession_number):
        id_0, id_1 = accession_number.split(":")
        return id_0, id_1


class SourceAccessionToGroupingComponent(odin.Mapping):
    from_obj = SourceAccession
    to_obj = ArchivesSpaceArchivalObject

    mappings = (
        ("title", None, "title"),
        ("language", None, "language"),
    )

    @odin.map_field(from_field="url", to_field="external_ids", to_list=True)
    def url(self, value):
        return [ArchivesSpaceExternalId(external_id=value, source="aurora")]

    @odin.map_field(from_field=("extent_size", "extent_files"), to_field="extents", to_list=True)
    def extents(self, extent_size, extent_files):
        return map_extents(extent_size, extent_files)

    @odin.map_field(from_field="language", to_field="lang_materials", to_list=True)
    def lang_materials(self, value):
        return [map_language(value)]

    @odin.map_field(from_field=("start_date", "end_date"), to_field="dates", to_list=True)
    def dates(self, date_start, date_end):
        return map_dates(date_start, date_end)

    @odin.map_list_field(from_field="rights_statements", to_field="rights_statements", to_list=True)
    def rights_statements(self, value):
        return [SourceRightsStatementToArchivesSpaceRightsStatement.apply(v) for v in value]

    @odin.map_field(from_field="resource", to_field="resource")
    def resource(self, value):
        return ArchivesSpaceRef(ref=value)

    @odin.map_list_field(
        from_field=("access_restrictions", "use_restrictions", "description", "appraisal_note", "language"),
        to_field="notes", to_list=True)
    def notes(self, access_restrictions, use_restrictions, description, appraisal_note, languages):
        data = []
        for text, type in [
                (access_restrictions, "accessrestrict"),
                (use_restrictions, "userestrict"),
                (description, "scopecontent"),
                (appraisal_note, "general_note")]:
            if text:
                data.append(map_note_multipart(text, type))
        return data


class SourceTransferToTransferComponent(odin.Mapping):
    from_obj = SourceTransfer
    to_obj = ArchivesSpaceArchivalObject

    @odin.map_field(from_field="metadata", to_field="title")
    def title(self, value):
        return value.title

    @odin.map_field(from_field="url", to_field="external_ids", to_list=True)
    def url(self, value):
        return [ArchivesSpaceExternalId(external_id=value, source="aurora")]

    @odin.map_field(from_field="metadata", to_field="language")
    def language(self, value):
        return 'mul' if len(value.language) > 1 else value.language[0]

    @odin.map_field(from_field="metadata", to_field="lang_materials", to_list=True)
    def lang_materials(self, value):
        return [map_language(lang) for lang in value.language]

    @odin.map_field(from_field="metadata", to_field="extents", to_list=True)
    def extents(self, value):
        extent_size, extent_files = value.payload_oxum.split(".")
        return map_extents(extent_size, extent_files)

    @odin.map_field(from_field="metadata", to_field="dates", to_list=True)
    def dates(self, value):
        return map_dates(value.date_start, value.date_end)

    @odin.map_list_field(from_field="rights_statements", to_field="rights_statements", to_list=True)
    def rights_statements(self, value):
        return [SourceRightsStatementToArchivesSpaceRightsStatement.apply(v) for v in value]

    @odin.map_field(from_field="resource", to_field="resource")
    def resource(self, value):
        return {"ref": value}

    @odin.map_list_field(from_field="metadata", to_field="notes", to_list=True)
    def notes(self, value):
        data = []
        if value.internal_sender_description:
            data.append(map_note_multipart(value.internal_sender_description, "scopecontent"))
        return data

    @odin.map_field(from_field="parent", to_field="parent")
    def parent(self, value):
        if value:
            return ArchivesSpaceRef(ref=value)


class SourcePackageToDigitalObject(odin.Mapping):
    from_obj = SourcePackage
    to_obj = ArchivesSpaceDigitalObject

    def extract_id(self, uri):
        return uri.rstrip("/").split("/")[-1]

    @odin.map_field(from_field="storage_uri", to_field="digital_object_id")
    def digital_object_id(self, value):
        return self.extract_id(value)

    @odin.map_field(from_field=("storage_uri", "use_statement"), to_field="file_versions", to_list=True)
    def file_versions(self, storage_uri, use_statement):
        return [ArchivesSpaceFileVersion(file_uri=storage_uri, use_statement=use_statement)]
