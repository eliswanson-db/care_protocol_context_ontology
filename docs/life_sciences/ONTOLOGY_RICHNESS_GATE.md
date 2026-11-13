# Ontology richness gate — Clinical Study lab (checked 2026-11-12)

**Question.** Is an open-standards ontology rich enough that the graph solves problems Genie Ontology and RAG
cannot? This is the go/no-go for ADR-0022. **Verdict: PASS**, with the gaps below.

The probes ran locally on pinned releases (see `src/standards/life_sciences/standards_manifest.yaml`).

## Candidates measured

| Source | Release | What it has | Verdict |
|---|---|---|---|
| NCI Thesaurus (NCIt) | 26.10d | 180k+ concepts. Metabolic and drug concepts are **is-a only**: Obesity C3283 sits under "Sign" / "CTRP Clinical Finding" with 10 leaf children and **0 forward roles**. Semaglutide C152328 is under "GLP-1 Mimetic" with **0 roles**. T2DM C26747 has roles to anatomic sites only. | **Code backbone only.** CDISC CT codes are NCIt C-codes, so it anchors terms. It is not the reasoning graph. |
| MONDO | 2026-11-03 | 32,137 active disease terms. **10,807 (34%) have more than one parent.** Depth 5–12 on the demo concepts (T2DM 7, MTC 12, MEN2A 10). 8,213 MeSH xrefs, plus NCIt / ICD-10-CM / DOID xrefs. | **Disease backbone.** |
| MED-RT | 2026.11.02 | **17 typed relations, about 100k edges**: may_treat 15,529 · has_PE 12,207 · CI_with 11,556 · has_MoA 7,999 · may_prevent 2,793 · CI_ChemClass 1,989 · CI_MoA 464 · CI_PE 277 · induces 170. | **Drug backbone.** |
| MeSH | 2026 | 31,110 descriptors and 61,794 concepts. Maps MED-RT's MeSH *concept* UIs (M…) to the *descriptor* UIs (D…) that MONDO xrefs use: 11,510 / 11,556 CI_with edges map. | **Bridge vocabulary.** |
| CDISC COSMoS | main@41fdf29, package 2026-11-02 | 1,588 Biomedical Concepts with hierarchy up to 4 levels. **Body Weight C81328 ⊏ Weight C25208.** The `WEIGHT` VS Dataset Specialization constrains `VSORRESU ∈ {LB, g, kg}` and requires VSTESTCD, VSTEST, VSORRES, VSORRESU and VSDTC. | **Concept → SDTM variable layer.** |
| CDISC SDTM CT | file last-modified 2026-09-25 | 47,243 rows. VSTESTCD WEIGHT C25208, BMI C16358, HEIGHT C25347, WSTCIR C100948 (codelist C66741). | **Controlled terms.** |
| CDISC USDM | DDF-RA (MIT code / CC BY 4.0 content) | Study → objective → endpoint → encounter/timing windows. | **Study-design layer.** |

## Cross-ontology paths verified (the reason to build the graph)

Enforced by `tests/test_ls_kb_paths.py` on the vendored KB (`kb_concept.csv`/`kb_edge.csv`, ~3.9k concepts,
~6.2k direct edges).

**Sound contraindication walk (broadening only):** participant MH (MONDO) `is_a*` → ancestor → equivalent MeSH record
→ broader MeSH records (SCR `headingMappedTo` descriptor, `broaderDescriptor`) → MeSH concept ← `CI_with` ← drug →
`has_MoA` / `memberOf` class. The walk never steps *down* to a narrower record; if it did, a sibling disease would
inherit contraindications it doesn't have. A test enforces that: small-cell lung carcinoma, another neuroendocrine
carcinoma, must not reach the MTC contraindication.

- **MEN2A (MONDO:0008234)** → MeSH D018813 → `CI_with` ← dulaglutide, liraglutide, semaglutide, … (GLP-1 RA MoA).
- **Medullary thyroid carcinoma (MONDO:0015277)**: MONDO has **no MeSH xref** for it, yet the MED-RT
  contraindication sits on MeSH SCR C536914 "Thyroid cancer, medullary". A single **curated, namespaced**
  equivalence (`cpl:curatedEquivalent`, `kb_curated_edges.csv`, with its reason) closes the gap. The route then
  reaches **semaglutide and dulaglutide only**.
- **MED-RT is not uniform across the GLP-1 RA class.** Tirzepatide and orforglipron carry the MTC contraindication
  on the *familial* MTC record (C536911) rather than C536914. From the familial-MTC leaf (MONDO:0007958, which has
  its own xref) the walk reaches five class members; from MTC itself it reaches two. Class-level propagation
  ("contraindicated for one member → review the class") is a genuine graph inference, and the inconsistency is a
  curation finding to show.
- **T2DM (MONDO:0005148)** → D003924 → `may_treat` ← GLP-1 RAs and others. This is the indication path.
- **Polyhierarchy:** the weight-related comorbidity roots cover 60+ members, 15+ of them with more than one parent.
  Counting distinct participants therefore needs closure semantics, not a union of flat lists.

## Graph problems the demo will pose (a test of retrieval *mechanism*, not of missing content)

**Knowledge parity (ADR-0025).** Every approach gets the same direct facts: each `is_a`, xref, `CI_with`,
`has_MoA`, `has_PE`, BC → DSS → variable link, and rule parameter. The graph stores them as triples. RAG gets them as
one generated reference entry per concept plus the protocol/SAP documents. Genie gets them as governed UC tables,
comments and Pages. Neither the graph nor RAG gets a pre-computed transitive closure; only the closure approach
materializes one, and that is its mechanism. So when an approach misses one of these, the cause is how it retrieves
and combines facts, not that it never had them.

| # | Problem | What the retrieval mechanism has to do |
|---|---|---|
| G1 | **Eligibility:** BMI ≥27 **and** ≥1 weight-related comorbidity (MONDO class: hypertension, hyperlipidemia, T2DM/prediabetes, ASCVD, HF, stroke, PAD, MASLD; carve-outs for pulmonary and pregnancy-induced hypertension and congenital coronary malformations) | MH is coded at leaves (e.g. familial hypercholesterolemia → familial hyperlipidemia → hyperlipidemia; 112 members, 51 with multiple parents). Membership is `is_a*` **minus** the carve-out subtrees, and exclusion wins when parents disagree (idiopathic PAH reaches heart failure through one parent and pulmonary hypertension through another). RAG has the same facts but must chain hops and apply the exception. Genie has the same tables but must write recursive SQL with an anti-join. **Honest gap:** MONDO does not place hypertensive heart disease under hypertensive disorder, so it is not a member. The demo shows this as an ontology gap; it is never used as a trick question. |
| G2 | **Exclusion by contraindication:** "history of MTC or MEN2, or any condition contraindicated for the study drug class" | Four hops across three vocabularies (MONDO → MeSH → MED-RT → MoA class), with subsumption at both ends. Every hop is written down in each approach; what differs is the ability to join across them. |
| G3 | **Prohibited concomitant medication by mechanism:** any GLP-1 RA, or any `Appetite Suppression [PE]` agent (29 drugs in MED-RT) | CM records (RxNorm) → MED-RT MoA/PE. The protocol names classes, not products. This is an inverse lookup ("which drugs have this MoA") followed by a join to participants. |
| G4 | **Amendment 2 class expansion:** adds obstructive sleep apnea (not central sleep apnea) to the comorbidity class for new enrollment | The participants who change are exactly the difference of two closures. Both amendment texts are in RAG and the class definitions are in all three, so this tests set difference over derived membership. |
| G5 | **Concept → data lineage:** endpoint measures Body Weight C81328 → DSS `WEIGHT` → `VS.VSSTRESN` where `VSTESTCD='WEIGHT'` → physical column | Typed path across the COSMoS BC, DSS and physical layers. The DSS unit list doubles as the validation rule for unsupported units. |
| G6 | **Cross-study comparability:** Study A and Study B Week 24 endpoints | Both measure the same BC, but the timing windows and baseline rules differ. This is a structural comparison of two rule records, not a string match. |

Questions that only work because one approach holds extra content are **context-availability experiments**. They are
reported separately and never mixed into the mechanism comparison (prompt §15, ADR-0025).

## Known gaps (documented, not hidden)

- **MedDRA is licensed and not used.** Real SDTM MH/AE use MedDRA. This demo codes MH with MONDO plus ICD-10-CM xrefs. That's a labeled deviation.
- **The MeSH bridge is lossy.** Some MONDO terms (e.g. MTC) have no MeSH xref. Gaps are closed only with curated `cpl:` edges that carry a reason (`kb_curated_edges.csv`), never by inferring through a broader descriptor. MeSH Supplementary Concept Records (`supp2026`) are part of the bridge.
- **MED-RT is inconsistent across class members** (see semaglutide above). The demo surfaces this rather than patching it.
- **MED-RT licensing (resolved 2026-11-13).** MED-RT is a VA work posted publicly by NCI EVS. Its documentation says "some proprietary data requires licensing"; that refers to content distributed through the UMLS, which this demo does not use. **Only the public NCI EVS release is used.** Vendored associations are filtered to RxNorm/MeSH/MED-RT endpoints (no SNOMED CT targets), and the `Authority` qualifier is kept on each edge.
- **MED-RT "CI_with Drug Hypersensitivity" is product-specific.** Treating it as "any drug allergy excludes" would over-exclude. The class-contraindication rule lists it as an excluded target, with the reason (registry `CI-STUDY-DRUG-CLASS.excluded_ci_targets`, fixture FX-29).
- **The graph-only exclusion is real, not contrived.** Diabetic ketoacidosis is not on CSL-A's explicit exclusion list, but MED-RT records exenatide `CI_with` DKA. Under the any-class-member policy, only the MED-RT walk excludes it (fixture FX-25).
- **No weight-gain physiologic effect exists in MED-RT** (searched has_PE names). "Drugs associated with weight gain" would be a namespaced demo extension, not MED-RT.
