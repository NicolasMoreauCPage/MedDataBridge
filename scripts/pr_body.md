PR: feat(ui): UI redesign (buttons/alerts/modals, Tailwind build, accessibility)

This PR contains a first large batch of UI improvements and refactors. Summary of main changes:

- Add Tailwind build pipeline and generated CSS: `app/static/css/ui-redesign.build.css`
- Add small accessible UI JS helpers: `app/static/js/ui.js` (focus trap with return, toasts with aria-live)
- Add automated refactor scripts: `scripts/refactor_ui.py`, `scripts/convert_buttons_to_macro.py`
- Normalized button/alert/modal classes across templates and converted simple buttons to `components.button` macro for priority templates (Batch A)
- CI workflow added: `.github/workflows/build-tailwind.yml`

Files changed (high level):
- `app/static/css/ui-redesign.build.css`
- `app/static/js/ui.js`
- many templates under `app/templates/` updated to use normalized classes/macros
- `scripts/` (refactor & conversion scripts)
- `docs/UI_REDESIGN_PLAN.md`, `docs/UI_UX_AUDIT.md`, `README.md`

Testing notes & manual QA:
- Run `npm ci && npm run build:css` locally (CI runs this automatically on PR)
- Start server and verify modals, toasts, and key pages (lists/forms/hprim_cotation)

Follow-ups (suggested):
- Review ambiguous conversion cases listed in `scripts/convert_buttons_report.txt` (if any)
- Run Batch B conversion (rest of templates) if acceptable
- Manual review & visual QA, then merge

Detailed audit and recommendations are in `docs/UI_UX_AUDIT.md`.

---
Notes: this is a non-trivial UI refactor. Please review visually and test critical paths before merging.
