import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const template = readFileSync(
  new URL("../../app/templates/structure_search.html", import.meta.url),
  "utf8",
);
const workspace = readFileSync(
  new URL("../../app/static/js/structure-search-workspace.js", import.meta.url),
  "utf8",
);

test("structure search delegates its FHIR request to the shared HTTP client", () => {
  assert.match(template, /js\/structure-search-workspace\.js/);
  assert.match(workspace, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(workspace, /await fetch\(`\/fhir\/Location/);
});

test("interactive structure editing uses the shared HTTP client", () => {
  const source = readFileSync(
    new URL("../../app/static/js/structure-interactive.js", import.meta.url),
    "utf8",
  );
  assert.match(source, /window\.medbridgeHttp\.request\(/);
  assert.match(source, /window\.medbridgeHttp\.post\('\/api\/structure\/move'/);
  assert.doesNotMatch(source, /await fetch\(/);
});

test("structure dashboard delegates every API call to the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/structure_new.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/structure-dashboard-workspace.js", import.meta.url),
    "utf8",
  );
  const actions = readFileSync(new URL("../../app/static/js/structure-new-actions.js", import.meta.url), "utf8");
  assert.match(template, /js\/structure-dashboard-workspace\.js/);
  assert.match(source, /window\.medbridgeHttp\.get\(apiUrl\)/);
  assert.match(source, /window\.medbridgeHttp\.get\(\s*`\/api\/structure\/details/);
  assert.match(actions, /window\.medbridgeHttp\.post\(\s*'\/api\/structure\/bulk-action'/);
  assert.doesNotMatch(source, /\bfetch\(/);
  assert.doesNotMatch(actions, /\bfetch\(/);
});

test("structure dashboard workspace remains valid JavaScript", () => {
  const source = readFileSync(
    new URL("../../app/static/js/structure-dashboard-workspace.js", import.meta.url),
    "utf8",
  );

  assert.doesNotThrow(() => new Function(source));
});

test("structure dashboard delegates its bulk actions to an external page asset", () => {
  const template = readFileSync(new URL("../../app/templates/structure_new.html", import.meta.url), "utf8");
  const actions = readFileSync(new URL("../../app/static/js/structure-new-actions.js", import.meta.url), "utf8");
  assert.match(template, /js\/structure-new-actions\.js/);
  assert.match(template, /defer src="\{\{ url_for\('static', path='js\/structure-new-actions\.js'\) \}\}"/);
  assert.match(actions, /window\.medbridgeHttp\.post\(/);
  assert.doesNotMatch(actions, /\bfetch\(/);
});

test("structure wizard delegates template APIs to the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.get\('\/api\/structure\/templates'\)/);
  assert.match(source, /window\.medbridgeHttp\.get\(\s*`\/api\/structure\/templates\/\$\{templateId\}/);
  assert.match(source, /window\.medbridgeHttp\.post\(\s*'\/api\/structure\/apply-template'/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("structure wizard keeps only the latest template request and blocks navigation while loading", () => {
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(source, /let templateRequestToken = 0/);
  assert.match(source, /const requestToken = \+\+templateRequestToken/);
  assert.match(source, /if \(requestToken !== templateRequestToken\) return/);
  assert.match(source, /nextBtn\.disabled = currentStep === 1 && isTemplateLoading/);
  assert.match(source, /Chargement du modèle…/);
});

test("structure wizard prevents an empty structure from reaching generation", () => {
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(source, /function getStructureValidationError\(/);
  assert.match(source, /Ajoutez et nommez au moins un pôle avant de poursuivre/);
  assert.match(source, /Nommez le service \$\{serviceIndex \+ 1\}/);
  assert.match(source, /Nommez l’UF \$\{ufIndex \+ 1\}/);
  assert.match(source, /function focusValidationError\(validationError\)/);
  assert.match(source, /data-structure-field="uf:\$\{poleIndex\}/);
});

test("structure wizard announces its active step to assistive technologies", () => {
  const template = readFileSync(new URL("../../app/templates/structure_wizard.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(template, /js\/structure-wizard-workspace\.js/);
  assert.match(template, /aria-label="Progression de la création de structure"/);
  assert.match(template, /id="wizardProgressStatus" class="sr-only" aria-live="polite"/);
  assert.match(template, /aria-controls="wizardContent"/);
  assert.match(source, /stepEl\.setAttribute\('aria-current', 'step'\)/);
  assert.match(source, /Étape \$\{currentStep\} sur \$\{steps\.length\}/);
});

test("structure wizard warns before losing unsaved changes", () => {
  const template = readFileSync(new URL("../../app/templates/structure_wizard.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(template, /id="wizardDirtyStatus"/);
  assert.match(source, /function markDirty\(\)/);
  assert.match(source, /window\.addEventListener\('beforeunload'/);
  assert.match(source, /clearDirty\(\);\s*window\.location\.href = '\/structure'/);
});

test("analytics and metrics dashboards delegate their reads to the shared HTTP client", () => {
  const analytics = readFileSync(new URL("../../app/templates/analytics_dashboard.html", import.meta.url), "utf8");
  const analyticsWorkspace = readFileSync(
    new URL("../../app/static/js/analytics-dashboard-workspace.js", import.meta.url),
    "utf8",
  );
  const metrics = readFileSync(new URL("../../app/templates/metrics_dashboard.html", import.meta.url), "utf8");
  assert.match(analytics, /data-analytics-dashboard/);
  assert.match(analytics, /js\/analytics-dashboard-workspace\.js/);
  assert.match(analyticsWorkspace, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(analyticsWorkspace, /\bfetch\(/);
  assert.match(metrics, /window\.medbridgeHttp\.get\('\/api\/metrics\/dashboard'\)/);
  assert.doesNotMatch(metrics, /\bfetch\(/);
});

test("admission, patient sample and validation-rule interactions use the shared HTTP client", () => {
  const admission = readFileSync(new URL("../../app/templates/admission_wizard.html", import.meta.url), "utf8");
  const patient = readFileSync(new URL("../../app/templates/patient_form.html", import.meta.url), "utf8");
  const rules = readFileSync(new URL("../../app/templates/validation_rules.html", import.meta.url), "utf8");
  assert.match(admission, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(admission, /\bfetch\(/);
  assert.match(patient, /window\.medbridgeHttp\.get\('\/patients\/sample-identity'\)/);
  assert.doesNotMatch(patient, /\bfetch\('\/patients\/sample-identity'/);
  assert.match(rules, /window\.medbridgeHttp\.post\('\/api\/validation-rules', parsed\)/);
  assert.match(rules, /window\.medbridgeHttp\.get\('\/api\/validation-rules'\)/);
  assert.doesNotMatch(rules, /\bfetch\(/);
});

test("structure import uses the shared HTTP client while preserving multipart payloads", () => {
  const template = readFileSync(new URL("../../app/templates/structure_import.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/structure-import-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/structure-import-workspace\.js/);
  assert.doesNotMatch(template, /onclick=/);
  assert.match(source, /window\.medbridgeHttp\.request\('\/api\/structure\/import\/confirm'/);
  assert.match(source, /body: formData/);
  assert.doesNotMatch(source, /\bfetch\('\/api\/structure\/import\/confirm'/);
});

test("alert configuration delegates reads and mutations to the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/alert_config.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/alert-config-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/alert-config-workspace\.js/);
  assert.doesNotMatch(template, /onclick=|onchange=/);
  assert.match(source, /window\.medbridgeHttp\.get\('\/api\/alert-config\/rules'\)/);
  assert.match(source, /window\.medbridgeHttp\.request\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("GHT dashboard delegates supervision reads to the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/templates/ght_dashboard.html", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.get\('\/api\/endpoints'\)/);
  assert.match(source, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("bed plan delegates patient search and movement mutation to the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/plan_lits.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/plan-lits-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/plan-lits-workspace\.js/);
  assert.doesNotMatch(template, /onclick=/);
  assert.match(source, /window\.medbridgeHttp\.get\(/);
  assert.match(source, /window\.medbridgeHttp\.request\(`\/workflow\/\$\{venueId\}\/mouvement`/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("dossier type change uses the shared HTTP client for regular and forced changes", () => {
  const source = readFileSync(new URL("../../app/templates/dossier_type_change.html", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.request\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("location cartography delegates hierarchy reads to the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/templates/components/location_cartography.html", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("isolated dossier, scenario and contact actions use the shared HTTP client", () => {
  for (const relativePath of [
    "../../app/templates/dossier_detail.html",
    "../../app/templates/test_scenario_generator.html",
    "../../app/templates/scenarios/ej_config_list.html",
    "../../app/templates/contacts_list.html",
  ]) {
    const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
    assert.match(source, /window\.medbridgeHttp\.(get|post|request)\(/);
    assert.doesNotMatch(source, /\bfetch\(/);
  }
});

test("scenario import and conformity toggle use the shared HTTP client", () => {
  for (const relativePath of [
    "../../app/templates/scenario_import.html",
    "../../app/templates/conformity_home.html",
  ]) {
    const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
    assert.match(source, /window\.medbridgeHttp\.request\(/);
    assert.doesNotMatch(source, /\bfetch\(/);
  }
});

test("rapid cotation workflow delegates searches and mutations to the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/cotations/saisie_rapide.html", import.meta.url), "utf8");
  const history = readFileSync(new URL("../../app/static/js/cotations-history-workspace.js", import.meta.url), "utf8");
  assert.match(template, /js\/cotations-history-workspace\.js/);
  assert.match(template, /data-cotations-history-workspace/);
  assert.doesNotMatch(template, /<style>/);
  assert.match(template, /window\.medbridgeHttp\.get\(/);
  assert.match(template, /window\.medbridgeHttp\.post\(/);
  assert.match(history, /window\.medbridgeHttp\.post\("\/cotations\/api\/bulk"/);
  assert.match(history, /window\.medbridgeHttp\.request\(/);
  assert.match(history, /window\.PameliaUi\.confirm/);
  assert.doesNotMatch(template, /\bfetch\(/);
  assert.doesNotMatch(history, /\bfetch\(/);
});

test("legacy cotation list uses real bulk mutations and a dedicated workspace asset", () => {
  const template = readFileSync(new URL("../../app/templates/cotations/liste.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/cotations-list-workspace.js", import.meta.url), "utf8");
  assert.match(template, /data-cotations-list/);
  assert.match(template, /js\/cotations-list-workspace\.js/);
  assert.doesNotMatch(template, /<style>/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.doesNotMatch(template, /simulation UI/);
  assert.match(source, /window\.medbridgeHttp\.post\("\/cotations\/api\/bulk"/);
  assert.match(source, /URL\.createObjectURL/);
  assert.match(source, /window\.PameliaUi\.confirm/);
  assert.doesNotMatch(source, /simulation UI/);
});

test("generic form submissions delegate to the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/static/js/forms.js", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.request\(this\.form\.action/);
  assert.doesNotMatch(source, /await fetch\(this\.form\.action/);
  assert.match(source, /class DependentFieldsManager/);
  assert.match(source, /field\.setAttribute\('aria-invalid', 'true'\)/);
  assert.match(source, /error\.setAttribute\('role', 'alert'\)/);
});

test("frontend lint rejects direct await fetch outside the shared client", () => {
  const source = readFileSync(new URL("../../scripts/lint_frontend.mjs", import.meta.url), "utf8");
  assert.match(source, /await\\s\+\(\?:window\\\.\)\?fetch/);
  assert.match(source, /app\/static\/js\/http\.js/);
});

test("frontend asset inventory is available for dead-code review", () => {
  const source = readFileSync(new URL("../../scripts/inventory_frontend_assets.mjs", import.meta.url), "utf8");
  assert.match(source, /Assets JavaScript/);
  assert.match(source, /Assets non référencés par un template/);
  assert.match(source, /const assetPatterns = \[/);
  assert.match(source, /process\.exitCode = 1/);
});

test("legacy structure view delegates all API calls to the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/structure.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/structure-legacy-workspace.js", import.meta.url), "utf8");
  assert.match(template, /js\/structure-legacy-workspace\.js/);
  assert.match(template, /data-structure-legacy-workspace/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
  assert.match(source, /data-structure-action/);
});

test("patient AJAX deletion uses the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/static/js/patients.js", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.request\(form\.action/);
  assert.doesNotMatch(source, /\bfetch\(form\.action/);
});

test("scenario template workspace uses the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/static/js/scenario-template-workspace.js", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.post\(/);
  assert.match(source, /window\.medbridgeHttp\.request\(/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("movement workflow location autocomplete uses the shared HTTP client", () => {
  const source = readFileSync(new URL("../../app/templates/mouvement_workflow.html", import.meta.url), "utf8");
  assert.match(source, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(source, /await fetch\(`\/api\/mouvements\/location-search/);
});

test("cache dashboard uses the shared HTTP client", () => {
  const template = readFileSync(new URL("../../app/templates/cache_dashboard.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/cache-dashboard-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/cache-dashboard-workspace\.js/);
  assert.doesNotMatch(template, /onclick=/);
  assert.match(source, /window\.medbridgeHttp\.get\('\/api\/metrics\/cache'\)/);
  assert.doesNotMatch(source, /await fetch\('\/api\/metrics\/cache'\)/);
});

test("application shell delegates generated toast dismissal", () => {
  const source = readFileSync(new URL("../../app/static/js/base-behaviors.js", import.meta.url), "utf8");
  assert.match(source, /data-toast-dismiss=/);
  assert.match(source, /closest\('\[data-toast-dismiss\]'\)/);
  assert.doesNotMatch(source, /onclick="toastSystem\.dismiss/);
});
