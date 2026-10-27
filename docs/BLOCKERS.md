# Blockers

| # | Blocker | Detail | Recorded | Resolved |
|---|---------|--------|----------|----------|
| 1 | Network blocked: cannot clone NL2Bash | `git clone https://github.com/TellinaTool/nl2bash.git data/external/nl2bash` timed out at 60s, 120s, and 180s. Files were manually placed instead: `data/external/nl2bash/data/bash/all.nl`, `all.cm`, and license files. | 2026-10-22 | Yes — files manually placed, conversion completed successfully |

**Impact:** None — Phase 4 (NL2Bash converter + validator + import) completed successfully using manually placed files.

**Conversion result:** 80 rows written to `data/processed/nl2bash.jsonl`, all validation checks pass.
