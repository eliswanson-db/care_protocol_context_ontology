"""Single source of truth for the Clinical Study knowledge graph (ADR-0022 / ADR-0025).

scripts/ls_graph_build.py turns this spec into four artifacts that can't drift apart:
  src/ontology/life_sciences/clinical_study.owl.ttl     TBox (classes, properties, domains/ranges, provenance)
  src/ontology/life_sciences/clinical_study.r2rml.ttl   R2RML over the UC graph views (one TriplesMap per view)
  src/ontology/life_sciences/graph_views.sql            CREATE VIEW statements in <catalog>.clinical_study_graph
  docs/life_sciences/ONTOBRICKS_IMPORT.md               the UI mapping checklist (one row per view)

IRI convention = what Ontobricks itself compiles (checked against docs/ontology/ontobricks_compiled_mapping_v3.sql):
classes <NS>#Class, properties <NS>/prop, instances <NS>/Class/<ID>. Every node belongs to exactly ONE mapped
class, so a relationship's endpoints always use the same IRI prefix as their entities (the HEDIS republish bug).
Official identifiers are kept as the officialIri attribute (MONDO/MeSH/NCIt PURLs); MED-RT, CDISC CT codelists and
COSMoS have no stable public RDF IRIs, so none is invented for them.

What is deliberately NOT in the graph: eligibility outcomes, population flags and candidate decisions. Those are
computed answers; the graph must reach them from the inputs (MH/CM records + KB + rules) by traversal, otherwise a
graph "win" would just be reading the answer table (ADR-0025).
"""

from __future__ import annotations

from dataclasses import dataclass, field

NS = "https://clinical-study-lab.example/ontology"
GRAPH_SCHEMA = "clinical_study_graph"

# ------------------------------------------------------------------------------------------------ KB node classes
# KB concept (scheme, concept_type prefix) -> graph class. Order matters: first match wins.
KB_CLASS_RULES: list[tuple[str, str | None, str]] = [
    ("MONDO", None, "Disease"),
    ("RXNORM", None, "Drug"),
    ("MEDRT", None, "DrugClass"),
    ("MESH", "MeshConcept", "MeshConcept"),
    ("MESH", None, "MeshRecord"),
    ("MESH_SCR", None, "MeshRecord"),
    ("NCIT", None, "ReferenceConcept"),
    ("ICD10CM", None, "ReferenceConcept"),
    ("CDISC_CT", "Codelist", "Codelist"),  # exact type match (see kb_class)
    ("CDISC_CT", "CodelistTerm", "CodelistTerm"),
    ("COSMOS_BC", None, "BiomedicalConcept"),
    ("COSMOS_DSS", "DatasetSpecialization", "DatasetSpecialization"),
    ("COSMOS_DSS", "DSSVariableBinding", "DSSVariableBinding"),
    ("SDTM_VAR", "DatasetVariable", "DatasetVariable"),
    ("SDTM_VAR", "Domain", "SDTMDomain"),
]

OFFICIAL_IRI = {  # scheme -> SQL expression over `code` (only publishers with stable public IRIs)
    "MONDO": "concat('http://purl.obolibrary.org/obo/MONDO_', code)",
    "MESH": "concat('http://id.nlm.nih.gov/mesh/', code)",
    "MESH_SCR": "concat('http://id.nlm.nih.gov/mesh/', code)",
    "NCIT": "concat('http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#', code)",
    "CDISC_CT": "CASE WHEN concept_type = 'CodelistTerm' THEN "
    "concat('http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#', code) END",
}


def kb_class(scheme: str, concept_type: str) -> str | None:
    for s, t, cls in KB_CLASS_RULES:
        if s == scheme and (t is None or concept_type.split(":")[0] == t):
            return cls
    return None


def kb_class_case_sql() -> str:
    parts = []
    for s, t, cls in KB_CLASS_RULES:
        cond = f"scheme = '{s}'" + (f" AND split(concept_type, ':')[0] = '{t}'" if t else "")
        parts.append(f"WHEN {cond} THEN '{cls}'")
    return "CASE " + " ".join(parts) + " END"


def official_iri_sql() -> str:
    return "CASE " + " ".join(f"WHEN scheme = '{s}' THEN {e}" for s, e in OFFICIAL_IRI.items()) + " END"


# ------------------------------------------------------------------------------------------------ properties
@dataclass(frozen=True)
class Prop:
    name: str
    label: str
    comment: str
    source: str  # where the relation comes from (official predicate, source relation, or demo extension)
    official: str | None = None  # official predicate IRI this mirrors (rdfs:subPropertyOf annotation)
    datatype: bool = False
    xsd: str = "string"


# KB predicate (kb_edge.predicate) -> graph property
KB_PREDICATES: dict[str, Prop] = {
    "rdfs:subClassOf": Prop(
        "subClassOf",
        "is a",
        "Direct is-a edge from the source ontology (MONDO / MED-RT).",
        "MONDO is_a; MED-RT Parent Of",
        "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    ),
    "skos:exactMatch": Prop(
        "exactMatch",
        "exact match",
        "MONDO cross-reference asserted as equivalent (source=MONDO:equivalentTo).",
        "MONDO xref",
        "http://www.w3.org/2004/02/skos/core#exactMatch",
    ),
    "oboInOwl:hasDbXref": Prop(
        "hasDbXref",
        "database cross-reference",
        "MONDO cross-reference not asserted as equivalent (may be broader or narrower).",
        "MONDO xref",
        "http://www.geneontology.org/formats/oboInOwl#hasDbXref",
    ),
    "cpl:curatedEquivalent": Prop(
        "curatedEquivalent",
        "curated equivalent (demo extension)",
        "Demo-curated "
        "equivalence closing a missing MONDO->MeSH xref; each has a reason in "
        "kb_curated_edges.csv. NOT official content.",
        "demo extension",
    ),
    "mesh:broaderDescriptor": Prop(
        "broaderDescriptor", "broader descriptor", "MeSH tree parent (by tree number).", "MeSH tree numbers"
    ),
    "mesh:headingMappedTo": Prop(
        "headingMappedTo",
        "heading mapped to",
        "MeSH Supplementary Concept Record -> the descriptor it is indexed under.",
        "MeSH SCR HeadingMappedTo",
    ),
    "mesh:conceptOf": Prop(
        "conceptOf",
        "concept of",
        "MeSH concept -> the descriptor/SCR record it belongs to.",
        "MeSH ConceptList",
    ),
    "medrt:memberOf": Prop(
        "memberOfClass",
        "member of class",
        "RxNorm ingredient is a member of a MED-RT class (EPC/APC).",
        "MED-RT Parent Of",
    ),
    "medrt:has_MoA": Prop("hasMechanismOfAction", "has mechanism of action", "", "MED-RT has_MoA"),
    "medrt:has_PE": Prop("hasPhysiologicEffect", "has physiologic effect", "", "MED-RT has_PE"),
    "medrt:has_TC": Prop("hasTherapeuticCategory", "has therapeutic category", "", "MED-RT has_TC"),
    "medrt:CI_with": Prop(
        "contraindicatedWith",
        "contraindicated with (condition)",
        "Drug is contraindicated in "
        "the MeSH condition concept. Product-specific hypersensitivity is excluded by the study "
        "rule, not here.",
        "MED-RT CI_with",
    ),
    "medrt:CI_MoA": Prop(
        "contraindicatedWithMechanism", "contraindicated with mechanism", "", "MED-RT CI_MoA"
    ),
    "medrt:CI_PE": Prop("contraindicatedWithEffect", "contraindicated with effect", "", "MED-RT CI_PE"),
    "medrt:may_treat": Prop("mayTreat", "may treat", "", "MED-RT may_treat"),
    "medrt:may_prevent": Prop("mayPrevent", "may prevent", "", "MED-RT may_prevent"),
    "cdisc:inCodelist": Prop("inCodelist", "in codelist", "", "CDISC CT"),
    "cdisc:nciConcept": Prop(
        "nciConcept", "NCIt concept", "The NCIt concept behind a CDISC CT term (C-code).", "CDISC CT"
    ),
    "cosmos:specializes": Prop(
        "specializes", "specializes", "Dataset specialization of a biomedical concept.", "COSMoS DSS bc_id"
    ),
    "cosmos:hasVariableBinding": Prop("hasVariableBinding", "has variable binding", "", "COSMoS DSS"),
    "cosmos:constrains": Prop(
        "constrains", "constrains", "Binding -> the SDTM variable it constrains.", "COSMoS DSS sdtm_variable"
    ),
    "cosmos:usesCodelist": Prop("usesCodelist", "uses codelist", "", "COSMoS DSS codelist"),
    "cosmos:allowedValue": Prop(
        "allowedValue",
        "allowed value",
        "A CT term the variable may take under this specialization (value_list).",
        "COSMoS DSS value_list",
    ),
    "cosmos:assignedValue": Prop("assignedValue", "assigned value", "", "COSMoS DSS assigned_value"),
    "cosmos:inDomain": Prop("inDomain", "in domain", "", "COSMoS DSS domain"),
    "cosmos:ncitCode": Prop("ncitCode", "NCIt code", "", "COSMoS BC ncit_code"),
    "cosmos:parentBC": Prop("parentConcept", "parent biomedical concept", "", "COSMoS BC parent_bc_id"),
}

# Instance-data properties (demo-extension semantics; USDM-aligned names where USDM has the concept)
DATA_PROPS: dict[str, Prop] = {
    p.name: p
    for p in [
        Prop("versionOf", "version of", "Protocol version of a study (USDM StudyVersion).", "registry"),
        Prop("screenedFor", "screened for", "", "EDC subjects"),
        Prop("atSite", "at site", "", "EDC subjects"),
        Prop("hasMedicalHistory", "has medical history record", "", "SDTM-shaped MH"),
        Prop("hasConMed", "has concomitant medication record", "", "SDTM-shaped CM"),
        Prop(
            "codedAs",
            "coded as",
            "MH coded to MONDO / CM coded to RxNorm ingredient (MedDRA/WHODrug not used).",
            "SDTM-shaped MH/CM, CPL_ coding columns",
        ),
        Prop("hasObservation", "has observation", "", "SDTM-shaped VS"),
        Prop(
            "originatesFrom",
            "originates from",
            "Standardized observation -> raw EDC source record.",
            "lineage",
        ),
        Prop(
            "measures", "measures", "Observation or endpoint -> the biomedical concept measured.", "COSMoS BC"
        ),
        Prop(
            "conformsTo",
            "conforms to",
            "Observation -> the dataset specialization it is shaped by.",
            "COSMoS DSS",
        ),
        Prop(
            "hasUnit",
            "has unit",
            "Observation -> the CDISC CT unit term recorded (VSORRESU).",
            "CDISC CT VSRESU",
        ),
        Prop("forParticipant", "for participant", "", "gold_endpoint_result"),
        Prop(
            "derivedUnder",
            "derived under",
            "Endpoint result -> the approved rule version that produced it.",
            "gold_endpoint_result",
        ),
        Prop("usesBaselineObservation", "uses baseline observation", "", "gold_endpoint_result"),
        Prop("usesFollowupObservation", "uses follow-up observation", "", "gold_endpoint_result"),
        Prop("generatedBy", "generated by", "", "gold_endpoint_result"),
        Prop("versionOfEndpoint", "version of endpoint", "", "rule registry"),
        Prop("amends", "amends", "", "rule registry"),
        Prop("appliesTo", "applies to", "Rule -> the protocol version(s) it governs.", "rule registry"),
        Prop(
            "supportedBy", "supported by", "Rule -> the protocol/SAP section that states it.", "rule registry"
        ),
        Prop("endpointOf", "endpoint of", "", "rule registry"),
        Prop("usesSpecialization", "uses specialization", "", "rule registry"),
        Prop("usesPopulation", "uses population", "", "rule registry"),
        Prop("eligibilityOf", "eligibility rule of", "", "rule registry"),
        Prop("hasCriterion", "has criterion", "", "rule registry"),
        Prop("usesClass", "uses concept class", "", "rule registry"),
        Prop(
            "extendsClass",
            "extends class",
            "Amended class inherits the roots of the class it extends.",
            "rule registry",
        ),
        Prop("hasRoot", "has root", "Members are the root and everything under it (is_a*).", "rule registry"),
        Prop(
            "excludesRoot",
            "excludes root",
            "Carve-out: a term under this root is never a member (exclusion wins).",
            "rule registry",
        ),
        Prop("hasDrugClass", "has drug class", "", "rule registry"),
        Prop("hasProhibitedEffect", "has prohibited physiologic effect", "", "rule registry"),
        Prop(
            "excludesContraindicationTarget",
            "excludes contraindication target",
            "A MED-RT CI_with target the rule deliberately ignores (e.g. product-specific hypersensitivity).",
            "rule registry",
        ),
        Prop("sectionOf", "section of", "", "document corpus"),
        Prop("documentFor", "document for", "", "document corpus"),
    ]
}


# ------------------------------------------------------------------------------------------------ classes
@dataclass(frozen=True)
class Attr:
    prop: str
    column: str
    xsd: str = "string"
    comment: str = ""


@dataclass
class Cls:
    name: str
    label: str
    comment: str
    parent: str | None = None
    sql: str | None = (
        None  # entity view body (must yield ID, Label + attribute columns); KB classes generated
    )
    attrs: list[Attr] = field(default_factory=list)
    usdm: str | None = None  # USDM class this aligns with (informative only)


KB_ATTRS = [
    Attr("code", "code"),
    Attr("scheme", "scheme"),
    Attr("release", "release"),
    Attr("definition", "definition"),
    Attr("officialIri", "official_iri", "anyURI"),
]

C = "${catalog}"
CS, STD = f"{C}.clinical_study", f"{C}.clinical_study_standards"

CLASSES: list[Cls] = [
    # ---- knowledge (KB)
    Cls("KnowledgeConcept", "Knowledge concept", "Abstract parent of every vendored standards concept."),
    Cls("Disease", "Disease (MONDO)", "MONDO disease concept.", "KnowledgeConcept", attrs=KB_ATTRS),
    Cls("DrugConcept", "Drug concept", "Abstract parent of drugs and drug classes.", "KnowledgeConcept"),
    Cls("Drug", "Drug ingredient (RxNorm)", "RxNorm ingredient.", "DrugConcept", attrs=KB_ATTRS),
    Cls(
        "DrugClass",
        "Drug class (MED-RT)",
        "MED-RT class; classType = EPC, MoA, PE, APC, TC, HC or PK.",
        "DrugConcept",
        attrs=[*KB_ATTRS, Attr("classType", "class_type")],
    ),
    Cls(
        "MeshRecord",
        "MeSH record",
        "MeSH descriptor (D...) or supplementary concept record (C...).",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("recordType", "record_type")],
    ),
    Cls(
        "MeshConcept",
        "MeSH concept",
        "MeSH concept (M...), the unit MED-RT relations point to.",
        "KnowledgeConcept",
        attrs=KB_ATTRS,
    ),
    Cls(
        "ReferenceConcept",
        "Reference concept",
        "NCIt or ICD-10-CM concept referenced by a mapping.",
        "KnowledgeConcept",
        attrs=KB_ATTRS,
    ),
    Cls(
        "Codelist",
        "CDISC codelist",
        "CDISC Controlled Terminology codelist.",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("submissionValue", "notation")],
    ),
    Cls(
        "CodelistTerm",
        "CDISC codelist term",
        "CDISC CT term (submissionValue = what goes in the dataset).",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("submissionValue", "notation")],
    ),
    Cls(
        "BiomedicalConcept",
        "Biomedical concept (COSMoS)",
        "CDISC biomedical concept.",
        "KnowledgeConcept",
        attrs=KB_ATTRS,
    ),
    Cls(
        "DatasetSpecialization",
        "SDTM dataset specialization (COSMoS)",
        "",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("sdtmigRange", "notation")],
    ),
    Cls(
        "DSSVariableBinding",
        "Dataset-specialization variable binding",
        "One variable of one specialization, with its value constraints.",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("mandatory", "notation")],
    ),
    Cls(
        "DatasetVariable",
        "SDTM dataset variable",
        "Name and role only (SDTMIG text not vendored).",
        "KnowledgeConcept",
        attrs=[*KB_ATTRS, Attr("role", "notation")],
    ),
    Cls("SDTMDomain", "SDTM domain", "", "KnowledgeConcept", attrs=KB_ATTRS),
    # ---- study design (USDM-aligned)
    Cls(
        "Study",
        "Study",
        "Synthetic study.",
        usdm="Study",
        sql=f"SELECT study_id AS ID, title AS Label, phase, duration_weeks FROM {STD}.study",
        attrs=[Attr("phase", "phase"), Attr("durationWeeks", "duration_weeks", "integer")],
    ),
    Cls(
        "StudyVersion",
        "Protocol version",
        "A protocol version of a study (original or amended).",
        usdm="StudyVersion",
        sql=f"SELECT study_version_id AS ID, concat(study_id, ' protocol ', protocol_version) AS Label, "
        f"protocol_version, sap_version, effective_date, amendment, change_summary FROM {STD}.study_version",
        attrs=[
            Attr("protocolVersion", "protocol_version"),
            Attr("sapVersion", "sap_version"),
            Attr("effectiveDate", "effective_date", "date"),
            Attr("amendmentNumber", "amendment", "integer"),
            Attr("changeSummary", "change_summary"),
        ],
    ),
    Cls(
        "EndpointDefinition",
        "Endpoint",
        "Endpoint definition (what is measured, in whom, by which formula).",
        usdm="Endpoint",
        sql=f"SELECT DISTINCT endpoint_id AS ID, label AS Label, formula FROM {STD}.rule_version",
        attrs=[Attr("formula", "formula")],
    ),
    Cls(
        "EndpointRuleVersion",
        "Endpoint rule version",
        "One approved, executable version of an endpoint's "
        "derivation rules (baseline, visit window, selection, tie-breaker).",
        sql=f"SELECT endpoint_version AS ID, concat(endpoint_id, ' ', rule_version) AS Label, rule_version, "
        f"baseline_method, baseline_window_start, baseline_window_end, same_day_predose, target_offset_days, "
        f"window_half_width_days, tie_breaker, review_state, approved_by, approved_on, registry_version "
        f"FROM {STD}.rule_version",
        attrs=[
            Attr("ruleVersion", "rule_version"),
            Attr("baselineMethod", "baseline_method"),
            Attr("baselineWindowStartDay", "baseline_window_start", "integer"),
            Attr("baselineWindowEndDay", "baseline_window_end", "integer"),
            Attr("sameDayPredose", "same_day_predose"),
            Attr("targetOffsetDays", "target_offset_days", "integer"),
            Attr("windowHalfWidthDays", "window_half_width_days", "integer"),
            Attr("tieBreaker", "tie_breaker"),
            Attr("reviewState", "review_state"),
            Attr("approvedBy", "approved_by", comment="demo-fixture = seeded, not a real human review"),
            Attr("approvedOn", "approved_on", "date"),
            Attr("registryVersion", "registry_version"),
        ],
    ),
    Cls(
        "AnalysisPopulation",
        "Analysis population",
        "",
        usdm="AnalysisPopulation",
        sql=f"SELECT population_id AS ID, label AS Label, definition FROM {STD}.analysis_population",
        attrs=[Attr("populationDefinition", "definition")],
    ),
    Cls(
        "EligibilityRule",
        "Eligibility rule version",
        "",
        usdm="EligibilityCriterion (grouping)",
        sql=f"SELECT DISTINCT eligibility_rule_id AS ID, eligibility_rule_id AS Label, review_state, approved_by "
        f"FROM {STD}.eligibility_criterion",
        attrs=[Attr("reviewState", "review_state"), Attr("approvedBy", "approved_by")],
    ),
    Cls(
        "EligibilityCriterion",
        "Eligibility criterion",
        "",
        usdm="EligibilityCriterion",
        sql=f"SELECT concat(eligibility_rule_id, '.', criterion_id) AS ID, text AS Label, criterion_type, "
        f"params_json FROM {STD}.eligibility_criterion",
        attrs=[Attr("criterionType", "criterion_type"), Attr("parameters", "params_json")],
    ),
    Cls(
        "ConceptClass",
        "Concept class",
        "A versioned set of concepts defined by roots + carve-outs; membership "
        "is is_a* over the KB, never a flat list.",
        sql=f"SELECT class_id AS ID, label AS Label, scheme, registry_version FROM {STD}.concept_class",
        attrs=[Attr("scheme", "scheme"), Attr("registryVersion", "registry_version")],
    ),
    Cls(
        "Document",
        "Document",
        "Synthetic protocol / SAP / amendment / memo.",
        sql=f"SELECT document_id AS ID, title AS Label, doc_type, version, status, effective_date "
        f"FROM {CS}.doc_document",
        attrs=[
            Attr("documentType", "doc_type"),
            Attr("documentVersion", "version"),
            Attr("documentStatus", "status"),
            Attr("effectiveDate", "effective_date", "date"),
        ],
    ),
    Cls(
        "DocumentSection",
        "Document section",
        "",
        sql=f"SELECT section_id AS ID, concat(section_number, ' ', heading) AS Label, section_number "
        f"FROM {CS}.doc_section",
        attrs=[Attr("sectionNumber", "section_number")],
    ),
    # ---- participants and data
    Cls(
        "Site",
        "Site",
        "",
        sql=f"SELECT DISTINCT SITEID AS ID, SITEID AS Label, COUNTRY AS country FROM {CS}.silver_dm",
        attrs=[Attr("country", "country")],
    ),
    Cls(
        "Participant",
        "Study participant",
        "A screened subject (randomized or screen failure).",
        usdm="StudySubject",
        sql=f"SELECT USUBJID AS ID, USUBJID AS Label, AGE AS age, SEX AS sex, DMDTC AS screening_date, "
        f"CPL_SCREEN_OUTCOME AS screen_outcome, ARMCD AS arm_code, CPL_RANDDT AS randomization_date, "
        f"RFXSTDTC AS first_dose, CPL_EDC_ELIGIBLE AS edc_eligible FROM {CS}.silver_dm",
        attrs=[
            Attr("age", "age", "integer"),
            Attr("sex", "sex"),
            Attr("screeningDate", "screening_date", "date"),
            Attr("screenOutcome", "screen_outcome"),
            Attr("armCode", "arm_code"),
            Attr("randomizationDate", "randomization_date", "date"),
            Attr("firstDoseDateTime", "first_dose"),
            Attr(
                "edcRecordedEligible", "edc_eligible", comment="what the site recorded, not the rule outcome"
            ),
        ],
    ),
    Cls(
        "MedicalHistoryRecord",
        "Medical history record",
        "",
        sql=f"SELECT CPL_SOURCE_RECORD_ID AS ID, MHTERM AS Label, MHSTDTC AS start_date FROM {CS}.silver_mh",
        attrs=[Attr("startDate", "start_date")],
    ),
    Cls(
        "ConMedRecord",
        "Concomitant medication record",
        "",
        sql=f"SELECT CPL_SOURCE_RECORD_ID AS ID, CMTRT AS Label, CMSTDTC AS start_date, CMENDTC AS end_date "
        f"FROM {CS}.silver_cm",
        attrs=[Attr("startDate", "start_date"), Attr("endDate", "end_date")],
    ),
    Cls(
        "WeightObservation",
        "Body weight observation",
        "SDTM-shaped VS record, VSTESTCD = WEIGHT.",
        sql=f"SELECT CPL_OBS_ID AS ID, concat(USUBJID, ' ', VISIT, ' ', coalesce(VSDTC, '')) AS Label, VISIT AS visit, "
        f"VSDTC AS vsdtc, VSDY AS study_day, VSORRES AS orres, VSORRESU AS orresu, CPL_RAW_UNIT AS raw_unit, "
        f"VSSTRESN AS stresn_kg, VSSTAT AS vsstat, VSSEQ AS vsseq FROM {CS}.silver_vs WHERE VSTESTCD = 'WEIGHT'",
        attrs=[
            Attr("visit", "visit"),
            Attr("dateTime", "vsdtc"),
            Attr("studyDay", "study_day", "integer"),
            Attr("originalResult", "orres"),
            Attr("originalUnit", "orresu"),
            Attr("rawUnit", "raw_unit"),
            Attr("standardValueKg", "stresn_kg", "double"),
            Attr("status", "vsstat"),
            Attr("sequence", "vsseq", "integer"),
        ],
    ),
    Cls(
        "SourceRecord",
        "EDC source record",
        "Raw export row (bronze), by record id.",
        sql=f"SELECT CPL_SOURCE_RECORD_ID AS ID, CPL_SOURCE_RECORD_ID AS Label, CPL_SOURCE_FILE AS source_file "
        f"FROM {CS}.silver_vs WHERE VSTESTCD = 'WEIGHT'",
        attrs=[Attr("sourceFile", "source_file")],
    ),
    Cls(
        "EndpointResult",
        "Endpoint result",
        "One participant x endpoint x rule version (ADaM-shaped).",
        sql=f"SELECT concat(USUBJID, '.', endpoint_version) AS ID, concat(USUBJID, ' ', endpoint_version) AS Label, "
        f"result_status, PCHG AS pchg, PCHG_DISPLAY AS pchg_display, BASE AS base, AVAL_FU AS aval_fu, "
        f"exclusion_reason, reference_date, followup_target_date, analysis_population_status "
        f"FROM {CS}.gold_endpoint_result",
        attrs=[
            Attr("resultStatus", "result_status"),
            Attr("percentChange", "pchg", "double"),
            Attr("percentChangeDisplay", "pchg_display", "double"),
            Attr("baselineKg", "base", "double"),
            Attr("followupKg", "aval_fu", "double"),
            Attr("exclusionReason", "exclusion_reason"),
            Attr("referenceDate", "reference_date", "date"),
            Attr("targetDate", "followup_target_date", "date"),
            Attr("analysisPopulationStatus", "analysis_population_status"),
        ],
    ),
    Cls(
        "ExecutionRun",
        "Execution run",
        "Content-addressed: same rules + KB + data = same id.",
        sql=f"SELECT DISTINCT execution_run_id AS ID, execution_run_id AS Label, engine_version "
        f"FROM {CS}.gold_endpoint_result",
        attrs=[Attr("engineVersion", "engine_version")],
    ),
]
CLASS_BY_NAME = {c.name: c for c in CLASSES}


# ------------------------------------------------------------------------------------------------ relationships
@dataclass(frozen=True)
class Rel:
    prop: str
    subject: str
    object: str
    sql: str  # must yield source_id, target_id


DATA_RELS: list[Rel] = [
    Rel(
        "versionOf",
        "StudyVersion",
        "Study",
        f"SELECT study_version_id AS source_id, study_id AS target_id FROM {STD}.study_version",
    ),
    Rel(
        "screenedFor",
        "Participant",
        "Study",
        f"SELECT USUBJID AS source_id, STUDYID AS target_id FROM {CS}.silver_dm",
    ),
    Rel(
        "atSite",
        "Participant",
        "Site",
        f"SELECT USUBJID AS source_id, SITEID AS target_id FROM {CS}.silver_dm",
    ),
    Rel(
        "hasMedicalHistory",
        "Participant",
        "MedicalHistoryRecord",
        f"SELECT USUBJID AS source_id, CPL_SOURCE_RECORD_ID AS target_id FROM {CS}.silver_mh",
    ),
    Rel(
        "codedAs",
        "MedicalHistoryRecord",
        "Disease",
        f"SELECT CPL_SOURCE_RECORD_ID AS source_id, CPL_MONDO_ID AS target_id FROM {CS}.silver_mh "
        f"WHERE CPL_CODING_STATUS = 'RESOLVED'",
    ),
    Rel(
        "hasConMed",
        "Participant",
        "ConMedRecord",
        f"SELECT USUBJID AS source_id, CPL_SOURCE_RECORD_ID AS target_id FROM {CS}.silver_cm",
    ),
    Rel(
        "codedAs",
        "ConMedRecord",
        "Drug",
        f"SELECT CPL_SOURCE_RECORD_ID AS source_id, CPL_RXNORM_ID AS target_id FROM {CS}.silver_cm "
        f"WHERE CPL_CODING_STATUS = 'RESOLVED'",
    ),
    Rel(
        "hasObservation",
        "Participant",
        "WeightObservation",
        f"SELECT USUBJID AS source_id, CPL_OBS_ID AS target_id FROM {CS}.silver_vs WHERE VSTESTCD = 'WEIGHT'",
    ),
    Rel(
        "originatesFrom",
        "WeightObservation",
        "SourceRecord",
        f"SELECT CPL_OBS_ID AS source_id, CPL_SOURCE_RECORD_ID AS target_id FROM {CS}.silver_vs "
        f"WHERE VSTESTCD = 'WEIGHT'",
    ),
    Rel(
        "measures",
        "WeightObservation",
        "BiomedicalConcept",
        f"SELECT CPL_OBS_ID AS source_id, 'COSMOS_BC:C81328' AS target_id FROM {CS}.silver_vs WHERE VSTESTCD = 'WEIGHT'",
    ),
    Rel(
        "conformsTo",
        "WeightObservation",
        "DatasetSpecialization",
        f"SELECT CPL_OBS_ID AS source_id, 'COSMOS_DSS:WEIGHT' AS target_id FROM {CS}.silver_vs "
        f"WHERE VSTESTCD = 'WEIGHT'",
    ),
    Rel(
        "hasUnit",
        "WeightObservation",
        "CodelistTerm",
        f"SELECT v.CPL_OBS_ID AS source_id, k.concept_id AS target_id FROM {CS}.silver_vs v "
        f"JOIN {STD}.kb_concept k ON k.notation = v.VSORRESU AND k.concept_id LIKE 'CDISC_CT:C66770.%' "
        f"WHERE v.VSTESTCD = 'WEIGHT'",
    ),
    Rel(
        "forParticipant",
        "EndpointResult",
        "Participant",
        f"SELECT concat(USUBJID, '.', endpoint_version) AS source_id, USUBJID AS target_id FROM {CS}.gold_endpoint_result",
    ),
    Rel(
        "derivedUnder",
        "EndpointResult",
        "EndpointRuleVersion",
        f"SELECT concat(USUBJID, '.', endpoint_version) AS source_id, endpoint_version AS target_id "
        f"FROM {CS}.gold_endpoint_result",
    ),
    Rel(
        "usesBaselineObservation",
        "EndpointResult",
        "WeightObservation",
        f"SELECT concat(USUBJID, '.', endpoint_version) AS source_id, explode(split(baseline_observation_id, ',')) "
        f"AS target_id FROM {CS}.gold_endpoint_result WHERE baseline_observation_id IS NOT NULL",
    ),
    Rel(
        "usesFollowupObservation",
        "EndpointResult",
        "WeightObservation",
        f"SELECT concat(USUBJID, '.', endpoint_version) AS source_id, followup_observation_id AS target_id "
        f"FROM {CS}.gold_endpoint_result WHERE followup_observation_id IS NOT NULL",
    ),
    Rel(
        "generatedBy",
        "EndpointResult",
        "ExecutionRun",
        f"SELECT concat(USUBJID, '.', endpoint_version) AS source_id, execution_run_id AS target_id "
        f"FROM {CS}.gold_endpoint_result",
    ),
    Rel(
        "versionOfEndpoint",
        "EndpointRuleVersion",
        "EndpointDefinition",
        f"SELECT endpoint_version AS source_id, endpoint_id AS target_id FROM {STD}.rule_version",
    ),
    Rel(
        "amends",
        "EndpointRuleVersion",
        "EndpointRuleVersion",
        f"SELECT endpoint_version AS source_id, concat(endpoint_id, '.', amends) AS target_id FROM {STD}.rule_version "
        f"WHERE amends IS NOT NULL",
    ),
    Rel(
        "appliesTo",
        "EndpointRuleVersion",
        "StudyVersion",
        f"SELECT r.endpoint_version AS source_id, v.study_version_id AS target_id FROM {STD}.rule_version r "
        f"JOIN {STD}.study_version v ON v.study_id = r.study_id AND v.sap_version = r.sap_version",
    ),
    Rel(
        "supportedBy",
        "EndpointRuleVersion",
        "DocumentSection",
        f"SELECT s.rule_id AS source_id, d.section_id AS target_id FROM {STD}.rule_document_support s "
        f"JOIN {CS}.doc_section d ON d.document_id = s.document_id AND d.section_number = s.section "
        f"WHERE s.rule_kind = 'endpoint'",
    ),
    Rel(
        "endpointOf",
        "EndpointDefinition",
        "Study",
        f"SELECT DISTINCT endpoint_id AS source_id, study_id AS target_id FROM {STD}.rule_version",
    ),
    Rel(
        "measures",
        "EndpointDefinition",
        "BiomedicalConcept",
        f"SELECT DISTINCT endpoint_id AS source_id, biomedical_concept AS target_id FROM {STD}.rule_version",
    ),
    Rel(
        "usesSpecialization",
        "EndpointDefinition",
        "DatasetSpecialization",
        f"SELECT DISTINCT endpoint_id AS source_id, dataset_specialization AS target_id FROM {STD}.rule_version",
    ),
    Rel(
        "usesPopulation",
        "EndpointDefinition",
        "AnalysisPopulation",
        f"SELECT DISTINCT endpoint_id AS source_id, population AS target_id FROM {STD}.rule_version",
    ),
    Rel(
        "eligibilityOf",
        "EligibilityRule",
        "Study",
        f"SELECT DISTINCT eligibility_rule_id AS source_id, study_id AS target_id FROM {STD}.eligibility_criterion",
    ),
    Rel(
        "appliesTo",
        "EligibilityRule",
        "StudyVersion",
        f"SELECT DISTINCT c.eligibility_rule_id AS source_id, v.study_version_id AS target_id "
        f"FROM (SELECT eligibility_rule_id, study_id, explode(split(protocol_versions, ',')) AS pv "
        f"FROM {STD}.eligibility_criterion) c "
        f"JOIN {STD}.study_version v ON v.study_id = c.study_id AND v.protocol_version = c.pv",
    ),
    Rel(
        "supportedBy",
        "EligibilityRule",
        "DocumentSection",
        f"SELECT s.rule_id AS source_id, d.section_id AS target_id FROM {STD}.rule_document_support s "
        f"JOIN {CS}.doc_section d ON d.document_id = s.document_id AND d.section_number = s.section "
        f"WHERE s.rule_kind = 'eligibility'",
    ),
    Rel(
        "hasCriterion",
        "EligibilityRule",
        "EligibilityCriterion",
        f"SELECT eligibility_rule_id AS source_id, concat(eligibility_rule_id, '.', criterion_id) AS target_id "
        f"FROM {STD}.eligibility_criterion",
    ),
    Rel(
        "usesClass",
        "EligibilityCriterion",
        "ConceptClass",
        f"SELECT concat(eligibility_rule_id, '.', criterion_id) AS source_id, class_id AS target_id "
        f"FROM {STD}.eligibility_criterion WHERE class_id IS NOT NULL",
    ),
    Rel(
        "extendsClass",
        "ConceptClass",
        "ConceptClass",
        f"SELECT class_id AS source_id, extends AS target_id FROM {STD}.concept_class WHERE extends IS NOT NULL",
    ),
    Rel(
        "hasRoot",
        "ConceptClass",
        "Disease",
        f"SELECT class_id AS source_id, concept_id AS target_id FROM {STD}.class_root WHERE kind = 'root'",
    ),
    Rel(
        "excludesRoot",
        "ConceptClass",
        "Disease",
        f"SELECT class_id AS source_id, concept_id AS target_id FROM {STD}.class_root WHERE kind = 'exclude_root'",
    ),
    Rel(
        "hasDrugClass",
        "ConceptClass",
        "DrugClass",
        f"SELECT class_id AS source_id, concept_id AS target_id FROM {STD}.class_root "
        f"WHERE kind IN ('member_of_class', 'drug_class')",
    ),
    Rel(
        "hasProhibitedEffect",
        "ConceptClass",
        "DrugClass",
        f"SELECT class_id AS source_id, concept_id AS target_id FROM {STD}.class_root WHERE kind = 'physiologic_effect'",
    ),
    Rel(
        "excludesContraindicationTarget",
        "ConceptClass",
        "MeshRecord",
        f"SELECT class_id AS source_id, concept_id AS target_id FROM {STD}.class_root "
        f"WHERE kind = 'excluded_ci_target'",
    ),
    Rel(
        "sectionOf",
        "DocumentSection",
        "Document",
        f"SELECT section_id AS source_id, document_id AS target_id FROM {CS}.doc_section",
    ),
    Rel(
        "documentFor",
        "Document",
        "Study",
        f"SELECT document_id AS source_id, study_id AS target_id FROM {CS}.doc_document WHERE study_id IS NOT NULL",
    ),
]


def kb_rel_groups(concepts: list[dict], edges: list[dict]) -> dict[tuple[str, str, str], int]:
    """(kb predicate, subject class, object class) -> edge count, using the same class rules as the views."""
    by = {c["concept_id"]: c for c in concepts}
    out: dict[tuple[str, str, str], int] = {}
    for e in edges:
        s, o = by[e["subject"]], by[e["object"]]
        k = (
            e["predicate"],
            kb_class(s["scheme"], s["concept_type"]),
            kb_class(o["scheme"], o["concept_type"]),
        )
        out[k] = out.get(k, 0) + 1
    return out


# KB relationship views actually generated: (kb predicate, subject class, object class). The parity test asserts
# this equals the set of groups present in kb_edge, so a new KB relation can't silently miss the graph.
KB_RELS: list[tuple[str, str, str]] = [
    ("rdfs:subClassOf", "Disease", "Disease"),
    ("rdfs:subClassOf", "DrugClass", "DrugClass"),
    ("skos:exactMatch", "Disease", "MeshRecord"),
    ("skos:exactMatch", "Disease", "ReferenceConcept"),
    ("oboInOwl:hasDbXref", "Disease", "MeshRecord"),
    ("oboInOwl:hasDbXref", "Disease", "ReferenceConcept"),
    ("cpl:curatedEquivalent", "Disease", "MeshRecord"),
    ("mesh:broaderDescriptor", "MeshRecord", "MeshRecord"),
    ("mesh:headingMappedTo", "MeshRecord", "MeshRecord"),
    ("mesh:conceptOf", "MeshConcept", "MeshRecord"),
    ("medrt:memberOf", "Drug", "DrugClass"),
    ("medrt:has_MoA", "Drug", "DrugClass"),
    ("medrt:has_MoA", "DrugClass", "DrugClass"),
    ("medrt:has_PE", "Drug", "DrugClass"),
    ("medrt:has_PE", "DrugClass", "DrugClass"),
    ("medrt:has_TC", "Drug", "DrugClass"),
    ("medrt:has_TC", "DrugClass", "DrugClass"),
    ("medrt:CI_with", "Drug", "MeshConcept"),
    ("medrt:CI_MoA", "Drug", "DrugClass"),
    ("medrt:CI_PE", "Drug", "DrugClass"),
    ("medrt:may_treat", "Drug", "MeshConcept"),
    ("medrt:may_treat", "DrugClass", "MeshConcept"),
    ("medrt:may_prevent", "Drug", "MeshConcept"),
    ("cdisc:inCodelist", "CodelistTerm", "Codelist"),
    ("cdisc:nciConcept", "CodelistTerm", "ReferenceConcept"),
    ("cosmos:specializes", "DatasetSpecialization", "BiomedicalConcept"),
    ("cosmos:hasVariableBinding", "DatasetSpecialization", "DSSVariableBinding"),
    ("cosmos:constrains", "DSSVariableBinding", "DatasetVariable"),
    ("cosmos:usesCodelist", "DSSVariableBinding", "Codelist"),
    ("cosmos:allowedValue", "DSSVariableBinding", "CodelistTerm"),
    ("cosmos:assignedValue", "DSSVariableBinding", "CodelistTerm"),
    ("cosmos:inDomain", "DatasetVariable", "SDTMDomain"),
    ("cosmos:ncitCode", "BiomedicalConcept", "ReferenceConcept"),
    ("cosmos:parentBC", "BiomedicalConcept", "BiomedicalConcept"),
]
