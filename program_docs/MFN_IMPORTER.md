MFN Importer — notes
====================

Purpose
-------
This importer reads MFN^M05 messages (location hierarchy) exported by CPAGE
and similar sources. It parses LOC/LCH/LRL segments, normalizes location
types and identifiers, and imports them into the database using a multi-pass
algorithm to resolve parent-child relations.

Key behaviors
-------------
- `_normalize_loc_type` converts common French labels and CPAGE codes to
  canonical short codes used in the model (M, ETBL_GRPQ, P, D, UF, UH, CH, LIT).
- The importer tries DB lookup for missing `loc_type`, then relation-based
  inference (e.g. parent of type UH → child is CH) before giving up.
- Multi-pass import retries pending entities up to 10 passes to resolve
  parent dependencies, and will create virtual poles/services when needed.

Testing
-------
- Unit tests for normalization and extraction are in `tests/test_mfn_heuristics.py`.
