This folder contains import reports produced by local tools.

Policy suggestion:
- `pam_import_report.json` is large and should be stored in Git LFS or moved to an artifacts store.
- We create a compact `pam_import_summary.json` which is safe to keep in the repository.

Files:
- `pam_import_report.json` — full per-file validation output (large).
- `pam_import_summary.json` — compact summary used for quick reviews and CI.
- `pam_import_report.json.gz` — compressed copy of the full report (kept if desired).

Recommended next steps:
1. Install Git LFS and track `reports/pam_import_report.json` (if your CI allows LFS):

   git lfs install
   git lfs track "reports/pam_import_report.json"

2. Alternatively, remove the full report from the git history and push it to external storage.
