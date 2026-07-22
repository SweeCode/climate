"""OED exposure ingestion: parse -> validate -> geocode -> code-map -> load.

This pipeline is shared across every peril and every product wedge, and it is where most
of the schedule goes: real bordereaux arrive with garbage geocodes, missing TIVs, and
inconsistent construction/occupancy codes. Ingesting messy client data cleanly — with a
validation report rather than a silent failure — is itself a competitive advantage.
"""

from data.ingest.oed_pipeline import (
    IngestionReport,
    Severity,
    ValidationIssue,
    ingest_oed_locations,
)

__all__ = ["IngestionReport", "Severity", "ValidationIssue", "ingest_oed_locations"]
