# Microsoft Fabric Phase 3 artifacts

This directory contains source-controlled implementation material for the Phase 3 ingestion layer.
It is not a fabricated Fabric export and contains no manually invented pipeline JSON.

- `notebooks/nb_bronze_ingestion_audit.py` is the single batched technical notebook. Attach it to
  `lh_bronze` and mark the four variables in its first cell as notebook parameters.
- `pipeline-build-spec.md` is the exact portal build specification for the six Data Factory
  pipelines. The live workspace remains the authoritative representation of each pipeline.

Native Fabric Git Integration is deliberately not configured in Phase 3. Repository artifacts are
therefore maintained alongside, but are not presented as exports of, the live Fabric items.
