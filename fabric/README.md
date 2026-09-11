# Microsoft Fabric artifacts

This directory contains source-controlled implementation material for the Phase 3 ingestion layer,
the Phase 4A/4B Silver production slice, and the Phase 5 production Gold MVP. It is not a
fabricated Fabric export and contains no manually invented pipeline JSON.

- `notebooks/nb_bronze_ingestion_audit.py` is the single batched technical notebook. Attach it to
  `lh_bronze` and mark the four variables in its first cell as notebook parameters.
- `pipeline-build-spec.md` is the exact portal build specification for the six Data Factory
  pipelines. The live workspace remains the authoritative representation of each pipeline.
- `notebooks/nb_bronze_to_silver.py` implements the audit-driven AtlasERP and MES Silver slice with
  typed Delta outputs, quarantine, and idempotent MERGE behavior.
- `silver-pipeline-build-spec.md` is the manual build and validation recipe for the independent
  `pl_transform_bronze_to_silver` pipeline. Tenant execution is not claimed by repository code.
- `notebooks/nb_silver_to_gold_production.py` implements the validated event-grain production star
  schema in `lh_gold` using deterministic full overwrite.
- `gold-pipeline-build-spec.md` is the manual build and validation recipe for the independent
  `pl_transform_silver_to_gold` pipeline. The Gold notebook and pipeline have not yet been
  published or executed in the tenant.

Native Fabric Git Integration is deliberately not configured. Repository artifacts are
therefore maintained alongside, but are not presented as exports of, the live Fabric items.
