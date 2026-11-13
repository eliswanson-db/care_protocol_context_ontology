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

**Path:** participant MH (MONDO leaf) `is_a*` → MONDO ancestor `xref` → MeSH D `concept` → M ← `CI_with` / `may_treat` ← drug → `has_MoA` → class.

- **MEN2A (MONDO:0008234)** → MeSH D018813 → `CI_with` ← albiglutide, dulaglutide, liraglutide, orforglipron, all with has_MoA GLP-1 receptor agonist. This is a direct cross-ontology contraindication.
- **Medullary thyroid carcinoma (MONDO:0015277)** has 29 ancestors. The relevant ones are "thyroid gland disorder" (D013959) and "carcinoma" (D002277), both with `CI_with` edges. A leaf-coded MH record is only caught through **variable-depth subsumption**.
- **Semaglutide.** NLM RxClass gives `CI_with` Thyroid Neoplasms (D013964) and MEN2A/2B. **MED-RT is not uniform across GLP-1 RA class members**: some are contraindicated at MEN2, others at Thyroid Neoplasms. Class-level propagation ("contraindicated for one member → review for the class") is a real graph inference. It also gives a curation-gap finding to show.
- **T2DM (MONDO:0005148)** → D003924 → `may_treat` ← 82 drugs, including 5 GLP-1 RAs. This is the indication path.
- **Obstructive sleep apnea** → D020181 (`may_treat`, 3 drugs). Its ancestor "sleep apnea syndrome" (D012891) has `CI_with` 4 drugs, so contraindications differ by level of the hierarchy.
- **Polyhierarchy:** OSA has 2 parents. Diabetic complications sit under both diabetes and the target-organ disorder. Counting distinct participants in "weight-related comorbidity" therefore needs closure semantics, not a union of flat lists.

## Graph problems the demo will pose (a test of retrieval *mechanism*, not of missing content)

**Knowledge parity (ADR-0025).** Every approach gets the same direct facts: each `is_a`, xref, `CI_with`,
`has_MoA`, `has_PE`, BC → DSS → variable link, and rule parameter. The graph stores them as triples. RAG gets them as
one generated reference entry per concept plus the protocol/SAP documents. Genie gets them as governed UC tables,
comments and Pages. Neither the graph nor RAG gets a pre-computed transitive closure; only the closure approach
materializes one, and that is its mechanism. So when an approach misses one of these, the cause is how it retrieves
and combines facts, not that it never had them.

| # | Problem | What the retrieval mechanism has to do |
|---|---|---|
| G1 | **Eligibility:** BMI ≥27 **and** ≥1 weight-related comorbidity (a MONDO class over hypertension, dyslipidemia, OSA, prediabetes/T2DM, CVD) | MH is coded at leaves ("hypertensive heart disease", "familial hypercholesterolemia"). Membership is `is_a*` over a polyhierarchy, 1–6 hops. The graph walks `subClassOf*`; the closure approach looks up a precomputed pair. RAG has the same `is_a` facts, but must retrieve and chain one entry per hop, and top-k similarity rarely returns the whole chain. Genie has the same edge table, but must write recursive SQL or find the right snippets. |
| G2 | **Exclusion by contraindication:** "history of MTC or MEN2, or any condition contraindicated for the study drug class" | Four hops across three vocabularies (MONDO → MeSH → MED-RT → MoA class), with subsumption at both ends. Every hop is written down in each approach; what differs is the ability to join across them. |
| G3 | **Prohibited concomitant medication by mechanism:** any GLP-1 RA, or any `Appetite Suppression [PE]` agent (29 drugs in MED-RT) | CM records (RxNorm) → MED-RT MoA/PE. The protocol names classes, not products. This is an inverse lookup ("which drugs have this MoA") followed by a join to participants. |
| G4 | **Amendment 2 class expansion:** adds a subtree (e.g. sleep apnea) to the comorbidity class | The participants who change are exactly the difference of two closures. Both amendment texts are in RAG and the class definitions are in all three, so this tests set difference over derived membership. |
| G5 | **Concept → data lineage:** endpoint measures Body Weight C81328 → DSS `WEIGHT` → `VS.VSSTRESN` where `VSTESTCD='WEIGHT'` → physical column | Typed path across the COSMoS BC, DSS and physical layers. The DSS unit list doubles as the validation rule for unsupported units. |
| G6 | **Cross-study comparability:** Study A and Study B Week 24 endpoints | Both measure the same BC, but the timing windows and baseline rules differ. This is a structural comparison of two rule records, not a string match. |

Questions that only work because one approach holds extra content are **context-availability experiments**. They are
reported separately and never mixed into the mechanism comparison (prompt §15, ADR-0025).

## Known gaps (documented, not hidden)

- **MedDRA is licensed and not used.** Real SDTM MH/AE use MedDRA. This demo codes MH with MONDO plus ICD-10-CM xrefs. That's a labeled deviation.
- **The MeSH bridge is lossy.** Some MONDO leaves (e.g. MTC) have no MeSH xref and resolve only through an ancestor. The graph shows the hop it used.
- **MED-RT is inconsistent across class members** (see semaglutide above). The demo surfaces this rather than patching it.
- **MED-RT licensing (resolved 2026-11-13).** MED-RT is a VA work posted publicly by NCI EVS. Its documentation says "some proprietary data requires licensing"; that refers to content distributed through the UMLS, which this demo does not use. **Only the public NCI EVS release is used.** Vendored associations are filtered to RxNorm/MeSH/MED-RT endpoints (no SNOMED CT targets), and the `Authority` qualifier is kept on each edge.
- **No weight-gain physiologic effect exists in MED-RT** (searched has_PE names). "Drugs associated with weight gain" would be a namespaced demo extension, not MED-RT.
