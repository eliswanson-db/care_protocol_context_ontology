**Build this as a “HEDIS Context and Evidence Lab”: one deterministic quality-measure pipeline, several interchangeable retrieval approaches, and an app that makes their evidence paths visible.** Keep Genie One as the business-user front door, but use a separate, controlled evaluation harness to distinguish improvements from semantics, ontology, retrieval, and orchestration.

Below is an implementation blueprint, roadmap, and a ready-to-paste coding-agent prompt. The most important design decision is to **share the underlying facts and measure calculations across approaches—not independently reimplement HEDIS in every agent.**

## Recommended scope

Start with **three diabetes-related evidence stories**, rather than the entire diabetes protocol:

| Story | Why it belongs |
|---|---|
| Glycemic status, GSD-oriented | Demonstrates local lab mapping, standardized observations, latest-result selection, thresholds, and metric semantics |
| Kidney evaluation, KED-oriented | Demonstrates evidence combinations, terminology relationships, missing mappings, and the difference between an order and completed testing |
| Eye examination, EED-oriented | Demonstrates structured evidence versus an outside report, document retrieval, extraction, and human-reviewed evidence acceptance |

GSD, KED, and EED are established HEDIS diabetes measure families, but the actual implementation must use the selected measurement-year specifications—not the background research as executable requirements. [wpcdn.ncqa](https://wpcdn.ncqa.org/www-prod/2026-HPR-List-of-Required-Performance-Measures_June-2025-Update.pdf)

**Working assumptions for the demo:**

- Synthetic patients and documents only; no production Epic connection initially.
- One selected measurement year, one explicit `as_of_date`, and versioned terminology.
- A provider-oriented, HEDIS-aligned demonstration unless licensed specifications, required data, and appropriate validation are available.
- Six carefully designed “golden threads” that visitors can follow end to end.
- The existing Hospital Control Tower is extended, not replaced.
- Native Genie experiences remain native; the custom app provides comparison, evidence inspection, and controlled experimentation.
- Full protocol adherence, pharmacy adherence, sepsis, and production reporting are later extensions.

The roadmap below is a proposed engineering plan, not a claim that the existing repositories already implement these features.

## Resolve these distinctions first

### Three different semantic layers

These should be visible as separate concepts in the demo:

| Layer | What it means here | Proposed implementation |
|---|---|---|
| Clinical terminology | What a clinical concept or observation means | SNOMED CT, LOINC, local-code mappings, value-set membership |
| Business and analytical semantics | What a metric means and how it aggregates | Deterministic measure evaluations, Unity Catalog metric views, comments, synonyms, Pages |
| Formal ontology and relationships | How entities, concepts, evidence, and policies relate | A small explicit ontology implemented in OntoBricks |

Unity Catalog semantics includes metric views, domains, Pages, certification, and deprecation; Genie Ontology combines this modeled context with inferred context from assets and usage. **That is not the same thing as an OWL/SNOMED clinical ontology.** [learn.microsoft](https://learn.microsoft.com/en-us/azure/databricks/ai-bi/release-notes/2026)

OntoBricks is the appropriate separate track for explicit graph modeling, mappings, supported reasoning, and graph access through MCP. Its published capabilities include OWL/R2RML-based modeling, graph materialization, GraphQL access, and MCP tools. [github](https://github.com/databrickslabs/ontobricks)

**The story to tell:** “These approaches solve related but different problems. Here is what each adds, and here is where combining them helps.”

### Measure logic versus context

**A Page or a comment can explain a measure. It must not be the only place that implements it.**

Recommended division:

- **Measure engine:** Determines eligibility, exclusions, numerator status, and accepted evidence.
- **Metric views:** Define reusable analytical measures and dimensions over the evaluated results.
- **Pages and comments:** Explain definitions, evidence rules, limitations, and authoritative sources.
- **Genie Agents:** Translate questions into curated analytical interactions.
- **Lakebase retrieval:** Finds relevant narrative evidence and policy documents.
- **OntoBricks:** Exposes relationships, concept mappings, and evidence paths.
- **Genie One:** Provides the business-facing orchestration experience.

Metric views centralize metric definitions and support querying from SQL, dashboards, Genie Agents, and other consumers. [docs.databricks](https://docs.databricks.com/aws/en/uc-semantics/metric-views/)

### HEDIS versus local policy

Several supplied research statements need to become **validation questions**, not hard-coded rules:

- A local type 2 diabetes cohort is not automatically the HEDIS denominator.
- A local “patient declined” exception must not automatically remove a member from a HEDIS denominator.
- An individualized clinical target must not silently replace a measure threshold.
- An ordered test is not a completed test.
- A result in a document is not automatically accepted reporting evidence.
- A missing result is not a reason to drop an otherwise eligible patient from a denominator.
- Age ranges, lookbacks, same-day selection rules, exclusions, GMI handling, and kidney-test pairing rules must come from the applicable specification.
- Coverage and continuous enrollment cannot be inferred from the existence of Epic encounters.
- Pharmacy orders alone should not be treated as dispensing or adherence evidence.

NCQA places licensing and certification conditions on commercial uses of HEDIS specifications and measure logic; calling something a demonstration does not itself resolve those obligations. Obtain an appropriate licensing review before distributing detailed specifications, value sets, or a commercial implementation. [ncqa](https://www.ncqa.org/programs/data-and-information-technology/hit-and-data-certification/measure-certification/)

For the initial build, use explicit labels such as:

> **Synthetic, HEDIS-aligned demonstration. Not NCQA-certified. Not for clinical decisions or official reporting.**

That label is a disclosure—not a substitute for licensing approval.

## Target architecture

```text
Synthetic Epic-shaped extracts + coverage/claims fixtures
Synthetic outside reports + local policy documents
Licensed terminology/specification inputs, when available
                         |
                         v
               Bronze: immutable source records
                         |
                         v
       Silver: normalized clinical events + terminology
            + mapping decisions + document assertions
                         |
                         v
        Deterministic, versioned measure evaluation
                         |
                         v
       Gold: patient-measure results + evidence links
              + reconciliation + provenance
                         |
          +--------------+------------------+
          |              |                  |
          v              v                  v
    UC semantics    Lakebase Search     OntoBricks
    Metric views    Document chunks     Explicit ontology
    Comments        BM25 + vectors      Graph mappings
    Pages           Version filters     Evidence paths
    Domains         Evidence citations  Read-only MCP
    Genie Agents
          |              |                  |
          +--------------+------------------+
                         |
                 Genie One front door
                         |
               Hospital Control Tower
             Evidence and evaluation tabs

Parallel:
Controlled evaluation harness -> MLflow -> benchmark results
Custom provenance store -> record-level evidence visualization
```

Lakebase Search supports vector search, BM25 keyword search, and hybrid combinations; its documented hybrid example uses reciprocal rank fusion rather than adding incompatible raw scores. [learn.microsoft](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-search)

OntoBricks deploys its web application and MCP companion as separate Databricks Apps through its bundle-based deployment. Plan for that additional app and identity boundary rather than assuming the existing Control Tower app can simply import its entire runtime. [github](https://github.com/databrickslabs/ontobricks/blob/master/docs%2Fdeployment.md)

### Avoid a circular architecture

Keep these directions distinct:

- **Inbound:** Genie One calls your custom MCP service.
- **Outbound:** Your evaluation harness calls Genie One or a Genie Agent.
- **Graph:** Genie One or the evaluation harness calls OntoBricks MCP.

Do not create a loop where Genie One calls your custom agent, which calls Genie One again without an explicit recursion guard.

Also distinguish a **tool exposed through MCP** from a **custom agent exposed through MCP**. The former executes a bounded operation; the latter may perform its own planning and multiple tool calls. They should not be benchmarked as if they have identical orchestration budgets.

## Build one context package

Create a small, version-controlled **context package** that produces multiple deployment artifacts.

```text
context/
  concepts/
  local_code_mappings/
  value_set_manifests/
  measure_definitions/
  protocol_definitions/
  business_terms/
  metric_views/
  genie_agents/
  pages/
  ontology/
  evaluation_cases/
```

The package should generate or validate:

- Unity Catalog table and column comments.
- Metric-view definitions and descriptive metadata.
- Genie Agent configuration and example SQL.
- Page content and domain-assignment manifests.
- OntoBricks ontology and mapping inputs.
- Document metadata and retrieval filters.
- Evaluation expectations and version manifests.

**Do not interpret “one source of truth” as one file containing everything.** Use a package of linked, typed artifacts with stable IDs and a release manifest.

Each release should record:

```text
context_release_id
measurement_year
as_of_date
measure_definition_versions
terminology_release_versions
value_set_versions
mapping_version
document_corpus_version
metric_definition_version
genie_configuration_version
ontology_version
git_commit
```

A metric definition, terminology release, and measure specification have different lifecycles. Preserve that separation.

## Design the clinical model

### Keep the first model narrow

Use a FHIR-inspired canonical model without implementing a full FHIR server or an entire OMOP conversion.

| Object | Required information |
|---|---|
| Patient | Synthetic identifier, demographics, source identifiers |
| Encounter | Setting, clinician, facility, service dates |
| Condition | Code system, code, status, onset/recorded dates |
| Observation | Local code, standard code, value, unit, status, clinically relevant timestamps |
| Order | Requested service, order status, order time |
| Coverage period | Payer/product, enrollment dates, known completeness |
| Claim or supplemental evidence | Service code, dates, source, acceptance status |
| Document | Patient linkage, author/source, document date, content hash, version |
| Evidence assertion | Extracted claim, supporting passage, confidence, review and acceptance state |
| Measure definition | Version, program, year, rule family, parameters, source/license metadata |
| Measure evaluation | Patient, version, denominator/numerator/exclusion state, evidence references |
| Protocol-step evaluation | Separate local-policy outcome and exception handling |

Do not combine `MeasureEvaluation` and `ProtocolStepEvaluation` into one ambiguous status field.

For example, a local protocol might accept a documented refusal as an exception while the selected quality measure does not. The model must be able to represent both outcomes without contradiction.

### Preserve multiple timestamps

For observations, retain at least:

```text
ordered_at
specimen_collected_at
observed_at
resulted_at
source_updated_at
ingested_at
```

The selected measure definition determines which timestamp matters. Do not make specimen collection time a universal rule merely because it appears in the initial research.

Also retain:

```text
result_status
correction_of_observation_id
source_record_id
source_record_version
raw_value
normalized_value
raw_unit
normalized_unit
mapping_id
mapping_version
```

### Separate unknown from failure

Use explicit states:

```text
MET
NOT_MET
EXCLUDED
NOT_ELIGIBLE
UNKNOWN
PENDING_REVIEW
```

For local protocol execution, additional states such as `MET_LATE` and `EXCEPTION` may be useful.

An enrollment-data gap should produce an explainable `UNKNOWN` or a clearly labeled provider-cohort result—not an invented health-plan denominator.

### Make calculation deterministic

For the demo, implement a handful of **tested rule families**, not a general-purpose CQL compiler:

- Latest accepted observation within a defined period.
- Required evidence combination.
- Approved exclusion evidence.
- Coverage qualification.
- Reviewed supplemental-evidence acceptance.

Allow configuration to select these rule families and validated parameters.

**Do not allow arbitrary natural-language measure descriptions to become executable production logic without review.**

## Use SNOMED and LOINC carefully

### Practical terminology scope

For the first demo:

- Use **LOINC** for relevant laboratory/observation identities.
- Use **SNOMED CT** for selected clinical concepts and relevant hierarchical relationships.
- Preserve original Epic/local codes.
- Represent value-set membership separately from terminology hierarchy.
- Add UCUM-aware unit handling where relevant.
- Add other code systems only when a selected evidence story requires them.

The SNOMED CT US Edition combines the US extension and international content and is distributed by NLM through its licensed terminology services. [nlm.nih](https://www.nlm.nih.gov/healthit/snomedct/us_edition.html)

LOINC download access and use are subject to its license; related artifacts can have additional content-specific conditions. [loinc](https://loinc.org/kb/license/)

### The LOINC ontology component

Your instinct about a “LOINC component” is well founded: the **LOINC Ontology** provides an interoperability solution using SNOMED CT’s ontological framework. A version 2.83 release was announced on October 21, 2026, with stated alignment to particular SNOMED and LOINC releases. [loinc](https://loinc.org/ontology)

Make this an **optional, bounded extension**, not a prerequisite for the entire demo:

1. Select the handful of laboratory concepts used in the golden threads.
2. Load a compatible, version-pinned terminology subset.
3. Preserve official identifiers and source relationships.
4. Demonstrate one meaningful relationship or query expansion.
5. Compare retrieval with and without that expansion.

The LOINC Ontology FAQ distinguishes use of the extension itself under the LOINC license from access to the underlying SNOMED International content; review the licenses of the actual packages being loaded rather than treating all terminology files as having identical conditions. [loinc](https://loinc.org/kb/ontology/faq)

### Important ontology guardrails

- Do not equate a local code to a standard concept based only on name similarity.
- Do not use `owl:sameAs` for every approximate mapping.
- Do not infer HEDIS value-set membership from a SNOMED ancestor relationship.
- Do not assume a LOINC hierarchy defines which tests satisfy a particular measure.
- Preserve mapping author, reviewer, confidence, method, and effective dates.
- Distinguish **asserted**, **inferred**, and **reviewed** relationships.
- Do not assume OntoBricks’ supported reasoning implements the full reasoning semantics of every imported clinical terminology.

OntoBricks advertises OWL 2 RL reasoning and SHACL validation; that is a specific capability set, not a guarantee of unrestricted clinical-ontology reasoning. [ontobricks](https://ontobricks.org/)

## Curate native Genie context

### Domain alignment

Use a small business-oriented structure:

| Domain/subdomain | Assets | Intended questions |
|---|---|---|
| Quality / Diabetes | Measure evaluations, quality metric views, definition Pages | “Where are the gaps?” |
| Clinical Evidence / Laboratory | Observations, orders, accepted evidence | “What evidence supports this result?” |
| Terminology / Mapping Quality | Mapping decisions, terminology references, mapping metrics | “Why did this local test not count?” |
| Hospital Operations | Existing operational assets | Existing Control Tower questions; optional cross-domain comparison |

Domains organize assets through governed tags; Pages belong to a domain or subdomain. These relationships need to be configured explicitly. [docs.databricks](https://docs.databricks.com/aws/en/uc-semantics/domains)

An **OntoBricks domain is a separate application concept**. Maintain an explicit mapping between business domains and OntoBricks domains; do not assume they synchronize automatically.

### Three initial Genie Agents

Current documentation uses **Genie Agents** for what were formerly called Genie Spaces. [docs.databricks](https://docs.databricks.com/aws/en/genie-agents/set-up)

Create:

| Genie Agent | Scope | Exclusions |
|---|---|---|
| Diabetes Quality | Evaluated measures and certified analytical definitions | No ad hoc reinterpretation of clinical notes |
| Clinical Evidence | Patient-specific evidence, observations, orders, and review state | No automatic reporting acceptance of unreviewed extraction |
| Terminology Quality | Local mappings, missing mappings, terminology versions, impacted records | No autonomous terminology approval |

Keep the existing operations agent separate initially.

Each agent should have:

- A narrow list of relevant assets.
- Explicit grain and join guidance.
- Tested example SQL.
- Definitions of ambiguous terms.
- Instructions for measurement year and `as_of_date`.
- An evidence-citation convention.
- Clear limits and abstention behavior.
- Its own regression questions.

Databricks recommends well-annotated data, tested example SQL, and benchmarks when preparing agents for API use; built-in benchmarks can compare generated results with a reference SQL answer. [docs.databricks](https://docs.databricks.com/aws/en/genie-agents/monitor)

### Pages worth authoring manually

Create these first:

- **Quality Measure Versus Clinical Protocol**
- **What Counts as Accepted Evidence**
- **Glycemic Status**
- **Kidney Evaluation**
- **Eye Examination Evidence**
- **Order Versus Completed Test**
- **Measurement Year and As-of Date**
- **Terminology Mapping Confidence**
- **Known Data Completeness**
- **Current Versus Historical Definitions**

Pages are authoritative business definitions that Genie One can prioritize and cite over inferred context. [docs.databricks](https://docs.databricks.com/gcp/en/uc-semantics/pages)

A useful Page template:

```text
Concept name
Business definition
Program and measurement-year applicability
Authoritative data assets
Accepted evidence
Evidence that is insufficient
Relevant terminology and value-set references
Known limitations
Owner and reviewer
Effective dates
Version and supersedes relationship
Related concepts
```

### Comments should carry precision

Example proposed table comment:

> One row per normalized clinical observation. An order is not an observation result. Qualifying evidence requires an accepted result status, an approved terminology mapping, and the date semantics specified by the applicable measure version.

Example proposed metric comment:

> Rate among the explicitly qualified denominator for the selected measure version and evaluation date. Unknown eligibility is reported separately. This synthetic demonstration is not an official HEDIS submission.

**Descriptions, formulas, synonyms, and trusted examples should agree.** Conflicting definitions across these surfaces should be treated as a failed deployment.

## Implement Lakebase retrieval

Use Lakebase for the **unstructured evidence and policy track**, not as an alternate place to invent population-level clinical calculations.

### Corpus design

Use deliberately small, authored documents:

- Synthetic outside eye-exam report.
- Local kidney-evaluation policy.
- Local lab-component mapping guide.
- Measure-definition explainer.
- Superseded policy version.
- Mapping change request and approval.
- A document with an intentionally ambiguous term.
- A document containing an instruction-like sentence to test prompt-injection resistance.

Store document and chunk metadata:

```text
document_id
document_version
chunk_id
patient_id, when applicable
domain_id
document_type
effective_start
effective_end
superseded_by
source_uri
content_hash
page_or_section
character_offsets
access_scope
corpus_release_id
```

### Retrieval variants

Implement interchangeable adapters:

- Keyword only.
- Vector only.
- Hybrid.
- Hybrid plus terminology expansion.
- Hybrid plus terminology expansion and a fixed reranker, if justified.

Lakebase’s documented extensions separate vector indexing from BM25 text indexing. Treat those as real deployment dependencies rather than assuming generic PostgreSQL full-text search is equivalent to the native BM25 path. [learn.microsoft](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-search)

Important implementation requirements:

- Keep embeddings and the query embedding model/version aligned.
- Use exact code lookup for identifiers where appropriate; do not rely solely on tokenization of strings such as `4548-4`.
- Apply patient, access, effective-date, and version filters to each candidate path.
- Preserve keyword rank, vector rank, fused rank, and reranker output separately.
- Do not add raw BM25 scores to cosine distances.
- Return the actual passage and source location.
- Return explicit freshness and corpus-version metadata.
- Test index maintenance and update behavior after corpus changes.

Unity Catalog data can be served into Lakebase through synced tables, which create a managed PostgreSQL copy; that introduces a synchronization boundary that should be visible in the demo. [docs.databricks](https://docs.databricks.com/aws/en/oltp/projects/sync-tables)

**Do not assume a synced copy automatically reproduces every source authorization behavior.** Verify end-user identity and effective access at each serving endpoint.

### Evidence is not acceptance

For the outside eye-exam report:

```text
Document retrieved
    -> assertion extracted
    -> patient/date/provider linkage checked
    -> review status recorded
    -> acceptance policy applied
    -> measure evaluation recomputed
```

The demo should clearly distinguish:

- “A relevant report was found.”
- “The report appears to contain qualifying evidence.”
- “The evidence was reviewed and accepted under this demo policy.”
- “The measure calculation changed.”

Those are four different events.

## Implement OntoBricks narrowly

### Initial ontology

Use a small graph with these classes:

```text
Patient
ClinicalObservation
LocalLabComponent
StandardClinicalConcept
TerminologyRelease
MappingDecision
ValueSetVersion
MeasureDefinition
MeasureVersion
MeasureEvaluation
EvidenceArtifact
EvidenceAssertion
SourceRecord
CoveragePeriod
ProtocolStep
```

Useful relationships:

```text
Patient -> hasObservation -> ClinicalObservation
ClinicalObservation -> originatesFrom -> SourceRecord
ClinicalObservation -> usesLocalComponent -> LocalLabComponent
LocalLabComponent -> hasMappingDecision -> MappingDecision
MappingDecision -> mapsTo -> StandardClinicalConcept
StandardClinicalConcept -> memberOf -> ValueSetVersion
MeasureVersion -> references -> ValueSetVersion
MeasureEvaluation -> evaluatedUnder -> MeasureVersion
MeasureEvaluation -> supportedBy -> EvidenceArtifact
EvidenceAssertion -> extractedFrom -> EvidenceArtifact
EvidenceAssertion -> reviewedUnder -> AcceptancePolicy
```

Make measure evaluations explicit graph entities. Do not attach a timeless `passesKED=true` property directly to a patient.

### What to demonstrate

Start with three graph questions:

1. “Why did this observation qualify as glycemic evidence?”
2. “Which patients and evaluations depend on this local-code mapping?”
3. “Which evidence assertions were derived from the superseded document?”

Use deterministic evaluation results as graph inputs. The graph explains and connects the results; it does not independently reconstruct the entire measure engine.

### MCP implementation cautions

OntoBricks’ documented MCP workflow includes domain selection, entity descriptions, ontology inspection, and GraphQL tools. Discover and test the deployed tool surface rather than inventing a generic `query_sparql` MCP tool. [github](https://github.com/databrickslabs/ontobricks/blob/master/docs/user-guide.md)

Its MCP companion and main app have separate deployment and identity considerations, including forwarded end-user identity in the documented deployment model. Test actual authorization end to end. [github](https://github.com/databrickslabs/ontobricks/blob/master/docs%2Fdeployment.md)

For this demo:

- Publish a read-only tool subset.
- Disable entity actions and rule-execution tools unless explicitly needed.
- Pin and record the active graph/domain version.
- Avoid shared mutable domain-selection state across concurrent users.
- Bound traversal depth and result size.
- Show whether an edge is asserted or inferred.
- Verify that each cited graph fact can be traced back to a source record or approved ontology artifact.

**Open-world caution:** lack of a graph edge must not automatically mean a patient has a care gap. Missing-evidence decisions belong to the explicitly scoped, deterministic evaluation logic.

OntoBricks is a source-available Databricks Labs project provided without formal support SLAs; present it as an exploratory implementation, not a supported native product feature with identical lifecycle guarantees. [github](https://github.com/databrickslabs/ontobricks)

## Create six golden threads

These are **proposed synthetic scenarios**, not patient facts or measured outcomes.

| Thread | Designed issue | Intended demonstration |
|---|---|---|
| GT-01: Unmapped A1c | A completed local lab result lacks an approved standard mapping | Terminology repair changes qualifying evidence without changing clinical care |
| GT-02: Order only | Kidney test was ordered but never resulted | Semantic precision prevents “ordered” from becoming “completed” |
| GT-03: Outside eye report | Relevant evidence exists only in a synthetic document | Hybrid retrieval finds the report; review governs acceptance |
| GT-04: Conflicting definitions | Old document conflicts with an approved current Page | Authority, versioning, and explicit conflict handling |
| GT-05: Definition change | Hypothetical local-policy version changes a threshold | Impact analysis, recomputation, semantic publication, regression tests |
| GT-06: Unknown enrollment | Clinical evidence exists but enrollment data is incomplete | Honest qualification limits and abstention |

Add a permissions variant to at least one thread: a user can see aggregate quality results but not a patient-specific report.

### A concrete trace example

For GT-01, author a synthetic observation such as:

```text
patient_id: SYN-P001
source_record_id: SYN-RESULT-001
local_component_id: LOCAL-A1C-POC
raw_value: 7.4
raw_unit: %
result_status: final
mapping_version: map-v1
mapping_status: unapproved
```

The first evaluation should report the missing approved mapping as an evidence problem.

A reviewed mapping release can then connect that component to an appropriate standard concept—for example, after validating the actual method and reporting convention. LOINC identifies `4548-4` as a standard HbA1c reporting code, while its guidance cautions against blindly selecting method-specific alternatives. [loinc](https://loinc.org/17856-6)

Trace the same item through:

```text
Source record
 -> Bronze row
 -> Silver observation
 -> Mapping decision
 -> Standard concept
 -> Value-set membership
 -> Measure evaluation
 -> Metric-view aggregate
 -> Genie answer
 -> Optional graph path
 -> App evidence card
```

The outcome changes because of an approved mapping—not because an LLM “decided the patient passed.”

## Make tracing a first-class feature

You need **three complementary forms of observability**:

| Type | Purpose | Implementation |
|---|---|---|
| Asset lineage | Which tables, columns, jobs, and analytical assets depend on each other | Native catalog lineage |
| Record-level provenance | Which exact source items supported this patient’s result | Custom evidence/provenance tables |
| Agent execution trace | Which tools ran, what they returned, and which response used them | MLflow plus adapter-level instrumentation |

Native lineage is valuable, but table/column lineage is not sufficient to explain one particular patient-result decision. Databricks documents column-level lineage; MLflow tracing captures application execution inputs, outputs, and intermediate steps. [docs.databricks](https://docs.databricks.com/sap/en/data-governance)

### Recommended provenance tables

```text
source_record
evidence_artifact
evidence_assertion
mapping_decision
measure_evaluation
measure_evaluation_evidence
provenance_edge
retrieval_event
retrieval_event_item
answer_evidence_link
```

Each relevant item should include:

```text
stable_id
version
run_id
source_snapshot_id
context_release_id
valid_time
recorded_time
content_hash, where applicable
```

An `answer_evidence_link` should connect the displayed answer to the actual evidence returned—not merely to every asset that could theoretically have helped.

### Honest observability

For each path, classify visibility as:

- **Observed:** Returned by the endpoint or recorded by your code.
- **Declared:** A configured dependency, not confirmed as used.
- **Unavailable:** Not exposed by the service.

Do not manufacture internal Genie retrieval spans or claim access to every snippet it considered.

The app should show tool calls, evidence, SQL, decisions, and observable citations—not hidden model reasoning.

## Benchmark in two layers

**Use MLflow for the shared evaluation backbone, with a notebook as an entry point—not as the entire implementation.** Add native Genie benchmarks for agent-specific regression testing.

MLflow supports versioned evaluation workflows, traces, and custom or built-in scorers; Genie’s own benchmarks provide a complementary way to test curated agents against expected SQL results. [mlflow](https://mlflow.org/genai/evaluations)

### Layer one: controlled components

Use adapters that can be called directly:

| Adapter | What it isolates |
|---|---|
| Deterministic SQL oracle | Reference calculations and expected evidence |
| Raw-schema analytical baseline | Limited-context analytical performance |
| Curated Genie Agent | Agent-specific metadata, examples, and semantic assets |
| Lakebase keyword/vector/hybrid | Retrieval changes under one corpus and answer generator |
| Custom SQL tool through MCP | Bounded structured retrieval through a custom interface |
| Custom agent through MCP | Agent planning plus its permitted retrieval tools |
| OntoBricks MCP | Graph-aware retrieval and relationship traversal |

The oracle is not a competing agent. It establishes correctness.

For retriever comparisons, hold constant:

```text
question
patient/data scope
data snapshot
corpus release
terminology release
answer-generation model
answer prompt
context budget
timeout
tool-call budget
```

Native agents may not expose all of those controls. Record the differences rather than claiming perfect equivalence.

### Layer two: end-to-end systems

Evaluate:

- Genie One with native governed assets.
- Genie One with the Lakebase MCP connector.
- Genie One with the custom-agent MCP connector.
- Genie One with the OntoBricks connector.
- Genie One with all approved approaches available.

Genie One supports external sources through MCP connectors, and custom MCP services can be connected through its external-source workflow. [docs.databricks](https://docs.databricks.com/gcp/en/ai-bi/release-notes/2026)

**Critical limitation:** Genie Ontology is not simply another retriever you can reliably call and switch off like your Lakebase adapter.

Use:

- Controlled context-publication stages.
- Restricted test identities and asset scopes.
- Separate clean environments where practical.
- Explicit tracking of inferred-context contamination.
- Observed citations and returned artifacts.
- Clear labels when an experiment is observational rather than causally isolated.

A prompt saying “use only this approach” is not proof that native context was excluded.

### Context ablation ladder

Use this proposed ladder where the surface supports it:

| Stage | Added context |
|---|---|
| C0 | Minimally descriptive schema |
| C1 | Table/column comments, grain, joins, terminology descriptions |
| C2 | Reusable metric definitions and synonyms |
| C3 | Curated Genie Agent instructions and examples |
| C4 | Pages, domains, and authority/certification signals |
| C5 | Terminology-aware retrieval or graph relationships |

Do not assume every surface consumes every stage identically. For example, direct Genie Agent behavior and Genie One’s use of Pages must be tested separately.

Also run **leave-one-component-out** experiments where practical. An incremental ladder alone can overstate the importance of the last component added.

### Score by question type

Avoid one undifferentiated leaderboard.

| Question type | Main tests |
|---|---|
| Population analytics | Exact denominator/numerator, result-set equivalence, correct grain |
| Definition questions | Correct version, source authority, conflict handling |
| Patient evidence | Correct patient, accepted evidence, dates, provenance |
| Graph/impact questions | Correct relationships and affected entities |
| Mixed questions | Appropriate routing and consistent synthesis |
| Insufficient-data questions | Correct uncertainty or refusal |
| Security questions | No unauthorized rows, passages, or facts |

A document-only retriever should not be penalized for refusing an unsupported population count. That refusal can be the correct behavior.

### Evaluation metrics

Prioritize deterministic checks:

- Correct patient set.
- Correct numerator and denominator.
- Correct evidence IDs.
- Correct measure and terminology versions.
- Correct exclusion and unknown states.
- Correct access scope.
- Correct refusal behavior.

Then add:

- Retrieval recall and ranking metrics for labeled document cases.
- Citation correctness and completeness.
- Answer groundedness.
- Context sufficiency.
- Routing appropriateness.
- Latency, tool calls, errors, and observed token usage.

MLflow’s retrieval-sufficiency judge requires appropriate retriever spans and ground-truth expectations. Do not label a native black-box tool response as a document-retrieval span solely to satisfy a scorer’s input contract. [mlflow](https://mlflow.org/docs/latest/genai/tracing/)

For unavailable native costs or internal retrieval metrics, record **not observable**, not zero.

### Test-set design

Proposed starting point:

- Six scripted golden threads.
- A separate development set.
- Roughly 60–100 held-out questions spanning the question types above.
- Several paraphrases and adversarial variants.
- Repeated runs for nondeterministic approaches.
- Separate cold-start and warm-run measurements.

These are planning targets, not claimed benchmark results.

Keep benchmark questions out of example SQL, Pages, and authored documents when the exact question would leak the answer.

## Extend the Control Tower

### Repository-specific cautions

The inspected Control Tower checkout was:

```text
f95ef692c44f408ad446826f4a1fab1bd994283e
```

The inspected OntoBricks checkout was:

```text
97b27c722dbb766348deb96b32df9c917f467eb5
```

Treat these as reproducibility anchors, not instructions to use them forever.

For the [Control Tower repository](https://github.com/eliswanson-db/hopital_control_tower), the inspected implementation has important extension points:

- The deployed app source is `app/`, including a React/Vite frontend and Flask backend.
- The repository also contains other source directories; the agent should inspect the bundle deployment path before editing similarly named modules.
- Existing startup logic can seed data and shift dates forward.
- Existing agent SQL tools use string/regex-based checks.
- Existing search configuration refers to encounter and SOP vector indexes.

**First corrective action:** disable date shifting and implicit startup mutation for the quality-demo data. A demo that silently moves historical results across a measurement-year boundary cannot support reproducible evaluation.

**Second corrective action:** separate read-only retrieval identity from administrative mutation. String checks are not a substitute for database privileges, parameterized operations, and properly constrained query execution.

### Proposed app tabs

| Tab | Purpose |
|---|---|
| Quality Overview | Rates, known denominator, unknowns, evidence gaps |
| Patient Evidence | Golden-thread timeline and supporting records |
| Context Explorer | Definitions, metric formulas, Pages, mappings, ontology relationships |
| Retrieval Lab | Same question through selected adapters |
| Trace Explorer | Source-to-answer provenance |
| Measure Drift | Proposed changes, impact, publication status, rollback |
| Existing Operations | Preserve the current Control Tower experience |

Use deep links from Genie One answers to the app where supported. Do not make unsupported embedding of the native Genie interface a prerequisite.

### Useful interaction design

Selecting a result should reveal:

```text
Question
Selected retrieval mode
Data and context versions
Answer
Supporting evidence
Rejected evidence and reasons
Observed tools and SQL
Source freshness
Evaluation score
Trace link
```

For the comparison view, show two or three approaches side by side—not seven columns of unreadable output.

## Demonstrate drift honestly

Separate three change types:

| Change | What should change |
|---|---|
| Definition wording or synonym | Pages/comments/agent guidance; numerical results should not change |
| Terminology mapping or value-set release | Evidence qualification and potentially downstream results |
| Measure logic or threshold | Evaluation outputs, aggregation semantics where relevant, explanatory context, tests |

**Updating a Page is not the same as updating a measure.**

### Recommended drift demonstration

Use two controlled changes:

**Mapping repair**

1. Show a completed test with an unapproved mapping.
2. Approve a versioned mapping.
3. Run impact analysis.
4. Recompute affected evaluations.
5. Refresh downstream serving artifacts.
6. Ask the same question again.
7. Show exactly why the answer changed.

**Hypothetical local-policy change**

1. Propose a threshold change in a local demonstration policy.
2. Label it clearly as hypothetical—not an announced HEDIS change.
3. Compare old/new patient classifications.
4. Run regression tests.
5. Publish a new context release.
6. Show old results remain reproducible.
7. Roll back.

The impact panel should show:

```text
Changed definition or mapping
Affected observations
Affected evaluations
Changed aggregate metrics
Updated Pages and agent configurations
Graph rebuild status
Lakebase synchronization watermark
Regression results
Approver
Publication timestamp
```

Keep an explicit `active_release` pointer, but retain immutable historical versions.

Do not promise instant native-context propagation. The app should distinguish **published**, **available in the serving copy**, and **observed in a new answer**.

## Manual versus automated work

| Work item | Coding agent can build | Human/admin responsibility |
|---|---|---|
| Repository discovery | Dependency map, deployment inspection, test inventory | Confirm intended workspace and deployment target |
| Synthetic fixtures | Deterministic authored cases and validation | Approve clinical plausibility and demo narrative |
| Measure implementation | Versioned deterministic code and tests | Approve specification interpretation |
| Terminology loader | Parsers, subset loader, manifests | Obtain access, accept licenses, approve mappings |
| UC semantics | Comments, metric definitions, export/deployment tooling | Ownership, permissions, certification approval |
| Pages/domains | Authoring artifacts and supported automation | Create/approve where APIs or permissions are unavailable |
| Genie Agents | Configuration, tested examples, benchmarks | Review and approve domain behavior |
| Lakebase Search | Schema, loaders, adapters, retrieval tests | Provisioning and project-setting approval |
| MCP services | Implementation, discovery, contract tests | Registration, credentials, sharing, tool policies |
| OntoBricks | Deployment preparation, ontology/mapping artifacts | App grants, active-domain approval, graph review |
| Evaluation | Harness, scoring, result views | Gold-label review and adjudication |
| Demonstration | Reset/preflight/replay tooling | Rehearsal and factual claims approval |

Do not let the coding agent “work around” unavailable permissions by broadening a service principal’s access or hard-coding credentials.

## Implementation roadmap

**Planning estimate:** an initial vertical slice in 1–2 weeks, followed by a fuller demonstration over roughly 4–6 weeks, assuming workspace access and timely clinical/admin review. Licensing or feature-access delays are outside that estimate.

| Phase | Deliverables | Exit gate |
|---|---|---|
| Discovery and capability gate | Repo analysis, runtime inventory, endpoint/tool discovery, manual checklist | One real query succeeds through each required available surface; unavailable capabilities documented |
| Deterministic foundation | Synthetic fixtures, Bronze/Silver/Gold, measure evaluations, provenance | Golden-thread calculations pass without an LLM |
| Native context | Metric views, comments, Pages, domains, three Genie Agents | Native answers reconcile to the SQL oracle |
| Retrieval and graph | Lakebase variants, custom MCP, OntoBricks domain/MCP | Each returns verifiable evidence with version metadata |
| Evaluation | MLflow integration, controlled runs, security tests, held-out cases | No fabricated evidence; results attributable to actual configurations |
| App and drift | New tabs, trace explorer, impact analysis, release/rollback | A visitor follows a fact end to end and observes a controlled update |
| Demo hardening | Preflight, deterministic reset, live/replay labels, runbook | Rehearsal succeeds from a clean state |

### Prioritize this vertical slice

Before completing every adapter, make this work:

```text
One synthetic patient
 -> one local A1c observation
 -> one mapping issue
 -> one deterministic evaluation
 -> one metric view
 -> one Genie Agent answer
 -> one record-level trace
 -> one approved mapping update
 -> one reproducible changed answer
```

Then add Lakebase and OntoBricks to that same story. This prevents parallel teams from producing impressive but disconnected demonstrations.

### Suggested ownership

- **Solution architect/demo owner:** Narrative, native experience, capability gates.
- **Data/AI engineer:** Pipelines, evaluation engine, retrieval adapters, MLflow.
- **App engineer:** Evidence and comparison UI, integration, deployment.
- **Clinical/quality reviewer:** Specification interpretation and expected results.
- **Workspace administrator:** Identity, permissions, Lakebase, MCP registration.

A smaller team can combine roles, but the clinical approval responsibility should remain explicit.

## Ready-to-paste coding prompt

The following prompt is intended to be supplied with this blueprint.

```text
You are the lead implementation engineer for a Databricks demonstration called
“HEDIS Context and Evidence Lab.”

Your job is to extend an existing Hospital Control Tower application and build
a reproducible, evidence-driven demonstration of:

1. Clinical terminology and local-code normalization.
2. Deterministic quality-measure evaluation.
3. Unity Catalog analytical/business semantics.
4. Genie Ontology and curated Genie Agents.
5. Unstructured retrieval using Lakebase Search.
6. A custom structured-retrieval tool and a custom agent exposed through MCP.
7. An OntoBricks explicit ontology/knowledge-graph implementation exposed by MCP.
8. Controlled evaluation and record-level source-to-answer tracing.
9. Governed updates when terminology or measure definitions change.

PRIMARY REPOSITORIES

Hospital Control Tower:
https://github.com/eliswanson-db/hopital_control_tower

OntoBricks:
https://github.com/databrickslabs/ontobricks

Previously inspected reproducibility anchors:
- Control Tower: f95ef692c44f408ad446826f4a1fab1bd994283e
- OntoBricks: 97b27c722dbb766348deb96b32df9c917f467eb5

Do not assume those commits are the versions installed in the target workspace.
Inspect the actual checkouts, record the chosen commits, and explain changes.

PRODUCT OUTCOME

A user starts in native Genie One, asks a diabetes quality question, and can:
- Obtain an answer grounded in governed analytical assets.
- Follow a specific patient/result/mapping/document through the pipeline.
- Compare appropriate retrieval approaches.
- See actual evidence, actual observable tool calls, and version metadata.
- Propose an approved mapping or local-policy change.
- Observe affected results and downstream context update.
- Reproduce the old answer under the old release.

Do not build a generic healthcare chatbot.
Do not redesign the entire existing application.

NONNEGOTIABLE BOUNDARIES

- Use synthetic patients and authored synthetic documents only.
- Clearly label all fixtures, screenshots, and outputs as synthetic.
- Do not claim NCQA certification or production HEDIS compliance.
- Do not copy licensed specifications, value sets, or terminology into a public
  repository without explicit approval.
- Never infer official measure rules from the research narrative alone.
- Do not treat an encounter-derived population as a complete health-plan
  denominator.
- Do not turn local protocol exceptions into quality-measure exclusions.
- Do not treat an order as a completed clinical event.
- Do not automatically accept an extracted document assertion as reportable
  evidence.
- Do not use LLM output as the authoritative measure calculation.
- Never fabricate endpoint behavior, citations, benchmark results, or native
  product internals.
- Never silently substitute one retrieval product for another.
- Never silently shift clinical dates to make a demo look current.
- Do not expose write/action tools to the business-user MCP path by default.
- Never expose credentials in frontend code, prompts, logs, or source control.

DISCOVERY FIRST

Inspect:
- Existing AGENTS.md and repository-specific instructions.
- Bundle files and actual source_code_path.
- Existing app framework, API routes, agent tools, deployment commands, and tests.
- Startup data seeding/date mutation.
- SQL execution and access-control implementation.
- Existing search/index configuration.
- OntoBricks deployment and MCP contracts at the selected version.

The previously inspected Control Tower deployed app source was app/, with a
React/Vite frontend and Flask backend. Verify before editing. Do not modify an
unused src/ copy and assume the app changed.

Produce:
- docs/current-state.md
- docs/architecture.md
- docs/capability-matrix.md
- docs/manual-setup.md
- docs/decisions.md
- An ordered backlog with dependencies and acceptance tests.

Create a read-only doctor/preflight command that verifies:
- Workspace authentication.
- SQL warehouse access.
- Catalog/schema privileges.
- Model/embedding endpoint access.
- Genie Agent API access.
- Genie One MCP or other supported evaluation access, if available.
- Lakebase connectivity and installed extensions.
- MCP discovery, transport, authentication, and allowed tools.
- OntoBricks active domain/version and accessible tools.
- MLflow experiment access.
- Serving-copy freshness.

Mark each capability AVAILABLE, MANUAL_SETUP_REQUIRED, or UNAVAILABLE.
A mock passing locally is not proof a remote feature is available.

If credentials are unavailable, implement contracts and clearly labeled fixture
mode, continue all unblocked work, and document the exact manual integration
test. Do not claim the live integration passed.

ARCHITECTURE

Build one shared data and calculation foundation:

Bronze immutable source records
 -> Silver normalized clinical events and mappings
 -> deterministic versioned measure evaluation
 -> Gold evaluations, aggregates, evidence links, and provenance.

Publish that foundation through:
- Unity Catalog metric views and descriptive metadata.
- Curated Genie Agents.
- Pages/domains and other supported native context artifacts.
- Lakebase document retrieval.
- Custom MCP tools/agent.
- OntoBricks graph mappings and MCP.

Genie One is the native business front door.
The custom app provides evidence inspection, experiments, and update controls.
The evaluation harness is independent of native UI automation.

Prevent recursion between Genie One and custom agents that call Genie One.

INITIAL SCOPE

Implement three evidence stories:
- GSD-oriented glycemic evidence.
- KED-oriented kidney evidence.
- EED-oriented outside eye-exam evidence.

Use local demonstration definitions unless approved, licensed, year-specific
measure specifications are provided.

Use one explicit measurement_year and as_of_date.
Label year-to-date results as nonfinal where applicable.

GOLDEN THREADS

Author six deterministic synthetic scenarios:
GT-01 Unmapped completed A1c.
GT-02 Kidney order without a completed result.
GT-03 Outside eye report requiring extraction and review.
GT-04 Superseded document conflicting with approved current context.
GT-05 Hypothetical local-policy definition change.
GT-06 Clinical evidence with unknown enrollment qualification.

Add a permissions variant to at least one thread.

Give every source record, observation, mapping, document, chunk, assertion,
measure evaluation, retrieval event, and answer stable identifiers.

DATA CONTRACTS

Model:
Patient, Encounter, Condition, Observation, Order, CoveragePeriod,
ClaimOrSupplementalEvidence, Document, EvidenceAssertion, MappingDecision,
MeasureDefinition, MeasureEvaluation, ProtocolStepEvaluation.

Preserve:
- Local code and standardized code.
- Raw and normalized value/unit.
- Order, collection, observation, result, update, and ingestion timestamps.
- Result/correction status.
- Source record ID/version.
- Mapping, terminology, value-set, and definition versions.
- Review/acceptance state.
- Data completeness.

Represent UNKNOWN separately from NOT_MET.
Keep protocol statuses separate from quality-measure statuses.

Create typed, versioned context artifacts.
Generate or validate comments, metric-view definitions, agent configs, Page
content, ontology inputs, and evaluation manifests from a shared context package.

Implement a small set of deterministic rule families.
Do not build a general CQL compiler or full FHIR server for this demo.

TERMINOLOGY AND ONTOLOGY

Use approved subsets of SNOMED CT and LOINC.
Preserve release metadata and source relationships.
LOINC Ontology integration is optional and must use compatible approved packages.

Do not:
- Manufacture standard codes or equivalences.
- Approve mappings based only on similar labels.
- Infer measure value-set membership from terminology ancestry.
- Use owl:sameAs for approximate relationships.
- Interpret absent graph edges as proof of missing care.
- Assume the graph reasoner implements all clinical-terminology semantics.

Build a bounded OntoBricks ontology for patients, observations, source records,
mapping decisions, concepts, value-set versions, measure versions, evaluations,
documents, and assertions.

Map deterministic results into the graph.
Make asserted versus inferred relationships visible.
Use real deployed MCP tool discovery.
Do not assume a SPARQL MCP endpoint exists.
Test domain-selection isolation across concurrent sessions.

NATIVE SEMANTICS

Create three curated Genie Agents:
- Diabetes Quality.
- Clinical Evidence.
- Terminology Quality.

Use narrow assets, clear grain and join rules, tested examples, abstention
instructions, and regression questions.

Author Pages for:
- Measure versus protocol.
- Accepted evidence.
- Glycemic status.
- Kidney evaluation.
- Eye evidence.
- Order versus completion.
- Measurement year/as-of date.
- Mapping confidence.
- Data completeness.
- Current versus historical definitions.

Do not assume Page/domain APIs or native publication hooks exist in the target
workspace. Use supported APIs when verified; otherwise generate complete
authoring artifacts and exact manual steps.

Version the agent configuration and context artifacts.
Use the actual current supported configuration schema, not an invented payload.
Validate configuration by round-trip readback and real test questions.

LAKEBASE RETRIEVAL

Implement keyword, vector, hybrid, and terminology-expanded hybrid adapters.

Use the native Lakebase Search extension path only after verifying availability.
If a fallback is needed, label it explicitly and keep its results separate.

Preserve document versions, effective dates, patient linkage, access scope,
content hashes, and source offsets.

Apply authorization and version filters within each candidate retrieval path.
Use rank fusion or another justified calibrated method.
Do not add incomparable raw scores.
Preserve each component rank/score for inspection.
Use exact lookup for standard codes when appropriate.
Pin embedding model/version/dimension.
Expose corpus and synchronization watermarks.

Return actual passages and citations.
A retrieved report creates an evidence candidate, not automatic acceptance.

MCP CONTRACTS

Define a shared request/result envelope across adapters.

Requests include:
question, optional patient scope, measurement year, as_of_date,
context release, requested mode, timeout, and correlation ID.

Results include:
answer or structured result,
actual evidence references,
source/configuration versions,
observable tool metadata,
freshness,
warnings,
latency,
and errors.

Expose bounded read-only operations such as:
- get_measure_definition
- get_patient_measure_evidence
- get_quality_metrics
- explain_mapping_impact
- search_clinical_documents

Separate bounded SQL tools from custom-agent orchestration.
Record actual available tool names from each deployed server.

Use least-privilege identities.
Verify end-user access at every endpoint.
Do not assume a service principal automatically preserves user-level policy.
Do not rely on SQL keyword checks as the security boundary.

TRACEABILITY

Implement source_record, evidence_artifact, evidence_assertion,
mapping_decision, measure_evaluation, measure_evaluation_evidence,
provenance_edge, retrieval_event, retrieval_event_item,
and answer_evidence_link.

Connect:
source -> normalized event -> mapping -> accepted evidence -> evaluation
 -> metric -> retrieved item -> answer.

Use native catalog lineage for asset dependencies.
Use custom provenance for record-level decisions.
Use MLflow for agent execution tracing.

Classify trace details as OBSERVED, DECLARED, or UNAVAILABLE.
Do not fabricate internal native retrieval spans.
Do not present private model reasoning as an observability feature.

EVALUATION

Implement the harness as reusable Python modules.
Use notebooks as thin execution/analysis entry points.

Support:
- Deterministic engine tests.
- Controlled retrieval tests.
- Context ablations.
- End-to-end Genie One tests where supported.
- Native Genie Agent benchmarks.
- Security/abstention tests.
- Drift regression tests.

Compare by question family, not one universal ranking.
Separate scripted golden threads from held-out evaluation questions.
Keep test answers out of training/example artifacts.

Use deterministic scorers for patient sets, numeric outputs, evidence IDs,
versions, exclusions, unknowns, and permissions.
Use LLM judges as supplementary checks.
Validate scorer span/input contracts.
Record unavailable native metrics as unobservable, not zero.
Do not claim causal isolation of native ontology effects unless the environment
actually supports it.

APP EXPERIENCE

Preserve existing operations functionality.

Add:
- Quality Overview.
- Patient Evidence.
- Context Explorer.
- Retrieval Lab.
- Trace Explorer.
- Measure Drift.

Show selected data/context versions and synthetic-data labels.
Comparison views must show actual evidence and observable execution differences.

Native Genie remains native. Use deep links rather than requiring unsupported
embedding.

DRIFT AND RELEASES

Support:
1. Approved terminology mapping repair.
2. Hypothetical local-policy logic change.
3. Metadata-only wording/synonym change.

Provide:
propose -> validate -> impact analysis -> approve -> recompute
 -> publish -> verify -> rollback.

Do not describe a hypothetical local-policy change as an official HEDIS change.
Preserve immutable historical outputs and an explicit active release pointer.
Distinguish publication from serving-copy freshness and observed answer uptake.

DELIVERABLES

- Extensible application changes.
- Data pipelines and deterministic evaluation modules.
- Typed context package.
- Retrieval adapters and MCP integrations.
- OntoBricks ontology/mapping artifacts.
- MLflow evaluation harness and entry notebooks.
- Golden fixtures and held-out evaluation set.
- Unit, integration, authorization, and regression tests.
- Capability manifest.
- Manual setup guide.
- Preflight, reset, and replay commands.
- Demo runbook and troubleshooting guide.
- Version lockfiles and deployment manifest.

EXECUTION STYLE

Work in small vertical slices.
For each slice:
1. State the acceptance test.
2. Implement the smallest working change.
3. Run relevant tests.
4. Report actual results.
5. List remaining manual blockers.

First implement:
one patient -> one observation -> one mapping issue -> one evaluation
 -> one metric -> one native agent answer -> one trace -> one approved update.

Only expand after that works.

Your first response should provide:
- Repository and capability findings.
- Assumptions and blockers.
- Proposed component boundaries.
- The first ten implementation tasks.
- The first vertical-slice acceptance test.

Do not respond with a giant unvalidated code dump.
Do not mark work complete based only on mocked integrations.
```

## Demo sequence

A strong live sequence is approximately:

1. **Start in Genie One:** Ask where diabetes quality gaps appear and request one explainable example.
2. **Open the patient evidence view:** Show a completed test that initially did not qualify.
3. **Follow the record:** Source row → normalized observation → missing mapping → evaluation.
4. **Compare retrieval:** Native analytical answer, document search, and graph relationship view.
5. **Show a different failure:** An order that never resulted, where correct semantics prevents false closure.
6. **Find outside evidence:** Retrieve the eye report, then show the distinction between extraction and acceptance.
7. **Repair a mapping:** Approve the change and display affected records and results.
8. **Demonstrate versioning:** Reproduce the old answer and show the new one.
9. **Open evaluation results:** Show held-out correctness, evidence quality, uncertainty handling, latency, and observed limitations.

The competitive message should be **demonstrated integration**, not an unsupported claim that another platform cannot do this: governed analytical definitions, native business interaction, interoperable MCP tools, operational document retrieval, explicit graph relationships, and evidence-driven evaluation working over a shared foundation. Databricks documents these capabilities across Unity Catalog semantics, Genie, MCP, Lakebase Search, and MLflow; the demo’s job is to prove how well the assembled implementation behaves. [docs.databricks](https://docs.databricks.com/gcp/en/uc-semantics/)
