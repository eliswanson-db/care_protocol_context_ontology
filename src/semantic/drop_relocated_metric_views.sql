-- One-time migration (ADR-0013, rev-4 relocation): drop the metric views left behind in the
-- BASE schema `care_protocol` after they were relocated to `care_protocol_semantic`.
--
-- Why this exists: the relocation deploy created the views in care_protocol_semantic but did NOT
-- remove the originals in care_protocol. Those stale base-schema metric views break the Ontobricks
-- entity scan — a plain SELECT against a metric view raises METRIC_VIEW_MISSING_MEASURE_FUNCTION,
-- which aborts the scan after the first entity (rev-3 / rev-5 notes in src/ontology/README.md).
--
-- Safe to run: the live copies exist and resolve in care_protocol_semantic (verified: GSD = 80.7%),
-- the `semantic` job now applies metric views ONLY into care_protocol_semantic, and no DAB-managed
-- consumer (Genie space, dashboards, Pages) references the base-schema copies. Idempotent (IF EXISTS).
-- A fresh workspace rebuild never creates these, so this is cleanup of the current workspace only.
--
-- Run: databricks bundle run ... OR paste on a SQL warehouse (profile ECT). Then re-run the
-- Ontobricks scan. Keep the Ontobricks source scope = care_protocol base tables + care_protocol_terminology;
-- it must NOT include care_protocol_semantic (else these views choke the scan in their new home).

DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.gsd_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.ked_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.bpd_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.spd_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.eed_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.mad_compliance_metrics;
DROP VIEW IF EXISTS eli_test_classic_catalog.care_protocol.protocol_adherence_metrics;
