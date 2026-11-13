---
name: Tool and retrieval routing (Clinical Study Lab)
synonyms: [which tool, routing, metric view, closure, graph, RAG, Genie, retrieval approach, where to look]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.gold_study_summary
  - eli_test_classic_catalog.clinical_study_standards.mondo_closure
---

| Question type | Best source |
|---|---|
| Endpoint numbers, counts, missingness, amendment impact | Gold tables / metric views (always filter study and rule version) |
| Why one participant's observation was selected or excluded | `gold_endpoint_candidate` + traceability Page |
| Is condition X a member of a concept class? | Closure tables (`mondo_closure`) or the knowledge graph (is_a*) |
| Is condition X contraindicated for the study drug class? | Knowledge graph (MONDO → MeSH → MED-RT, several hops) |
| What does the protocol / SAP say, and which version? | Protocol and SAP documents (cite document and section) |
| Is a rule approved? | `rule_version` / `rule_assertion` review state; a document statement alone is not enough |

Retrieved evidence and calculated results are different things: calculations come only from the deterministic
engine's gold tables, never from a language model recomputing them.
