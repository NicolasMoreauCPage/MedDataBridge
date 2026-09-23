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

test("structure dashboard delegates its generated tree actions", () => {
  const source = readFileSync(
    new URL("../../app/static/js/structure-dashboard-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(source, /data-structure-action="select-node"/);
  assert.match(source, /closest\('\[data-structure-action\]'\)/);
  assert.doesNotMatch(source, /onclick=/);
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

test("structure wizard delegates generated field and row actions", () => {
  const source = readFileSync(new URL("../../app/static/js/structure-wizard-workspace.js", import.meta.url), "utf8");
  assert.match(source, /data-wizard-action="remove-pole"/);
  assert.match(source, /wizardContent\?\.addEventListener\('change'/);
  assert.match(source, /wizardContent\?\.addEventListener\('click'/);
  assert.doesNotMatch(source, /onclick=|onchange=/);
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
  const metricsWorkspace = readFileSync(
    new URL("../../app/static/js/metrics-dashboard-workspace.js", import.meta.url),
    "utf8",
  );
  const base = readFileSync(new URL("../../app/templates/base.html", import.meta.url), "utf8");
  assert.match(analytics, /data-analytics-dashboard/);
  assert.match(analytics, /js\/analytics-dashboard-workspace\.js/);
  assert.match(analyticsWorkspace, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(analyticsWorkspace, /\bfetch\(/);
  assert.match(metrics, /js\/metrics-dashboard-workspace\.js/);
  assert.doesNotMatch(metrics, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(metrics, /\bonclick=/);
  assert.match(metricsWorkspace, /window\.medbridgeHttp\.get\("\/api\/metrics\/dashboard"\)/);
  assert.doesNotMatch(metricsWorkspace, /\bfetch\(/);
  assert.ok(base.indexOf("js/http.js") < base.indexOf("{% block content %}"));
});

test("admission, patient sample and validation-rule interactions use the shared HTTP client", () => {
  const admission = readFileSync(new URL("../../app/templates/admission_wizard.html", import.meta.url), "utf8");
  const patient = readFileSync(new URL("../../app/templates/patient_form.html", import.meta.url), "utf8");
  const patientWorkspace = readFileSync(
    new URL("../../app/static/js/patient-form-workspace.js", import.meta.url),
    "utf8",
  );
  const rules = readFileSync(new URL("../../app/templates/validation_rules.html", import.meta.url), "utf8");
  const rulesWorkspace = readFileSync(
    new URL("../../app/static/js/validation-rules-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(admission, /window\.medbridgeHttp\.get\(/);
  assert.doesNotMatch(admission, /\bfetch\(/);
  assert.match(patient, /js\/patient-form-workspace\.js/);
  assert.match(patient, /class="patient-form space-y-6"/);
  assert.doesNotMatch(patient, /<style>[\s\S]*?\.input-field[\s\S]*?<\/style>/);
  assert.doesNotMatch(patient, /window\.medbridgeHttp\.get\(/);
  assert.match(patientWorkspace, /window\.medbridgeHttp\.get\("\/patients\/sample-identity"\)/);
  assert.doesNotMatch(patientWorkspace, /\bfetch\(/);
  assert.match(rules, /js\/validation-rules-workspace\.js/);
  assert.doesNotMatch(rules, /window\.medbridgeHttp\./);
  assert.match(rulesWorkspace, /window\.medbridgeHttp\.post\("\/api\/validation-rules", parsed\)/);
  assert.match(rulesWorkspace, /window\.medbridgeHttp\.get\("\/api\/validation-rules"\)/);
  assert.doesNotMatch(rulesWorkspace, /\bfetch\(/);
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
  ]) {
    const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
    assert.match(source, /window\.medbridgeHttp\.(get|post|request)\(/);
    assert.doesNotMatch(source, /\bfetch\(/);
  }
  const contacts = readFileSync(new URL("../../app/templates/contacts_list.html", import.meta.url), "utf8");
  const contactsWorkspace = readFileSync(
    new URL("../../app/static/js/contacts-list-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(contacts, /js\/contacts-list-workspace\.js/);
  assert.match(contacts, /role="dialog" aria-modal="true"/);
  assert.doesNotMatch(contacts, /window\.medbridgeHttp\./);
  assert.match(contactsWorkspace, /window\.medbridgeHttp\.request\(/);
  assert.match(contactsWorkspace, /event\.key === "Escape"/);
  assert.doesNotMatch(contactsWorkspace, /\bfetch\(/);
});

test("scenario EJ configuration list delegates its deletion action", () => {
  const template = readFileSync(new URL("../../app/templates/scenarios/ej_config_list.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/scenario-ej-config-list.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/scenario-ej-config-list\.js/);
  assert.match(template, /data-delete-scenario-ej-config/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /window\.medbridgeHttp\.request\(/);
  assert.match(source, /window\.PameliaUi\?\.confirm/);
  assert.doesNotMatch(source, /\bfetch\(/);
});

test("EJ scenario status delegates its automatic filters", () => {
  const template = readFileSync(new URL("../../app/templates/scenarios/ej_scenarios_status.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/ej-scenarios-status.js", import.meta.url), "utf8");
  assert.match(template, /js\/ej-scenarios-status\.js/);
  assert.match(template, /data-ej-scenarios-filter/);
  assert.doesNotMatch(template, /\bonchange=/);
  assert.match(source, /requestSubmit\(\)/);
});

test("conformity message copy is delegated and announces its result", () => {
  const template = readFileSync(new URL("../../app/templates/conformity_message_detail.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/conformity-message-detail.js", import.meta.url), "utf8");
  assert.match(template, /js\/conformity-message-detail\.js/);
  assert.match(template, /id="copyRawMessageStatus" class="sr-only" aria-live="polite"/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /navigator\.clipboard\.writeText/);
  assert.match(source, /button\.disabled = true/);
  assert.match(source, /button\.disabled = false/);
});

test("message detail delegates payload copy with JSON bootstrap data", () => {
  const template = readFileSync(new URL("../../app/templates/message_detail.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/message-detail.js", import.meta.url), "utf8");
  assert.match(template, /id="hl7PayloadData" type="application\/json"/);
  assert.match(template, /js\/message-detail\.js/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /JSON\.parse\(data\.textContent\)/);
  assert.match(source, /navigator\.clipboard\.writeText/);
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

test("bulk scenario execution uses a dedicated workspace for its selection controls", () => {
  const template = readFileSync(new URL("../../app/templates/scenarios_bulk_execute_v2.html", import.meta.url), "utf8");
  const source = readFileSync(
    new URL("../../app/static/js/scenarios-bulk-execute-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/scenarios-bulk-execute-workspace\.js/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /\bonclick=|\bonchange=/);
  assert.match(source, /toggleAllScenariosBtn/);
  assert.match(source, /addEventListener\("click", toggleAllScenarios\)/);
  assert.match(source, /addEventListener\("change", updateSelectedCount\)/);
});

test("dossier cotation tabs are delegated and keyboard accessible", () => {
  const template = readFileSync(new URL("../../app/templates/dossier_cotations_detail.html", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../app/static/js/dossier-cotations-tabs.js", import.meta.url), "utf8");
  assert.match(template, /js\/dossier-cotations-tabs\.js/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(template, /role="tablist"/);
  assert.match(template, /role="tabpanel"/);
  assert.match(source, /event\.key === "ArrowRight"/);
  assert.match(source, /event\.key === "ArrowLeft"/);
  assert.match(source, /event\.key === "Home"/);
  assert.match(source, /event\.key === "End"/);
});
