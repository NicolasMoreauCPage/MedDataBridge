/* Poste de travail des modèles de scénarios : matérialisation et exécution. */
(function () {
  "use strict";

  function notify(message, kind = "info") {
    window.toastSystem?.show?.(message, kind === "warn" ? "warning" : kind);
  }

  function makeElement(tag, className, content) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }

  async function responseData(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || data.message || `Erreur HTTP ${response.status}`);
    }
    return data;
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    button.disabled = busy;
    button.classList.toggle("opacity-60", busy);
    button.classList.toggle("cursor-wait", busy);
    button.textContent = busy ? "Traitement en cours…" : label;
  }

  function resultPanel(workspace) {
    const panel = workspace.querySelector("#results");
    const content = workspace.querySelector("#resultContent");
    panel?.classList.remove("hidden");
    if (content) content.replaceChildren();
    return content;
  }

  function appendLink(parent, href, label) {
    const link = makeElement(
      "a",
      "inline-flex w-fit rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-700",
      label,
    );
    link.href = href;
    parent.append(link);
  }

  function renderMaterialization(workspace, data) {
    const content = resultPanel(workspace);
    if (!content) return;
    const scenario = data.scenario || {};
    const card = makeElement("section", "rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/30");
    card.append(makeElement("h4", "font-semibold text-emerald-900 dark:text-emerald-100", "Scénario créé"));
    card.append(makeElement("p", "mt-1 text-sm text-emerald-800 dark:text-emerald-200", `${scenario.name || "Scénario"} · ${scenario.step_count || 0} étape(s) · ${scenario.protocol || "format non précisé"}`));
    if (scenario.id) {
      const actions = makeElement("div", "mt-3");
      appendLink(actions, `/scenarios/${scenario.id}`, "Ouvrir et compléter le scénario");
      card.append(actions);
    }
    content.append(card);
  }

  function renderPlay(workspace, data) {
    const content = resultPanel(workspace);
    if (!content) return;
    const run = data.run || {};
    const card = makeElement("section", "rounded-xl border border-violet-200 bg-violet-50 p-4 dark:border-violet-800 dark:bg-violet-950/30");
    const isDryRun = Boolean(run.dry_run);
    card.append(makeElement("h4", "font-semibold text-violet-900 dark:text-violet-100", isDryRun ? "Prévisualisation terminée" : "Exécution lancée"));
    card.append(makeElement("p", "mt-1 text-sm text-violet-800 dark:text-violet-200", `${run.message_count || 0} livraison(s) · statut : ${run.status || "inconnu"}`));
    if (run.scenario_id && run.play_id) {
      const actions = makeElement("div", "mt-3");
      appendLink(actions, `/scenarios/${run.scenario_id}/plays/${run.play_id}`, "Ouvrir le suivi du jeu");
      card.append(actions);
    }
    content.append(card);

    if (Array.isArray(data.messages) && data.messages.length) {
      const list = makeElement("ul", "divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white text-sm dark:divide-slate-700 dark:border-slate-700 dark:bg-slate-800");
      data.messages.forEach((message, index) => {
        const item = makeElement("li", "flex flex-wrap items-center justify-between gap-2 p-3");
        item.append(makeElement("span", "font-medium text-slate-800 dark:text-slate-100", `Message ${index + 1}`));
        item.append(makeElement("span", "rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-200", `${message.status || "inconnu"}${message.ack ? ` · ACK ${message.ack}` : ""}`));
        list.append(item);
      });
      content.append(list);
    }
  }

  function renderError(workspace, message) {
    const content = resultPanel(workspace);
    if (content) content.append(makeElement("p", "rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200", message));
    notify(message, "error");
  }

  function refreshEndpointChoices(form) {
    const protocol = form.querySelector("[data-template-protocol]")?.value;
    const endpointSelect = form.querySelector("[data-template-endpoint]");
    const help = form.querySelector("[data-template-endpoint-help]");
    if (!endpointSelect) return;
    const compatibleKinds = protocol === "FHIR"
      ? new Set(["FHIR", "FILE", "FTP", "SFTP"])
      : new Set(["MLLP", "FILE", "FTP", "SFTP"]);
    let compatibleCount = 0;
    endpointSelect.querySelectorAll("option[data-endpoint-kind]").forEach((option) => {
      const compatible = compatibleKinds.has(option.dataset.endpointKind);
      option.disabled = !compatible;
      option.hidden = !compatible;
      if (compatible) compatibleCount += 1;
    });
    if (endpointSelect.selectedOptions[0]?.disabled) endpointSelect.value = "";
    if (help) {
      help.textContent = compatibleCount
        ? `${compatibleCount} destination(s) compatible(s) avec ${protocol === "FHIR" ? "FHIR" : "HL7 v2"}.`
        : `Aucune destination compatible avec ${protocol === "FHIR" ? "FHIR" : "HL7 v2"}.`;
    }
  }

  async function materialize(workspace, form, button) {
    const formData = new FormData(form);
    const payload = {
      protocol: formData.get("protocol"),
      ipp_prefix: formData.get("ipp_prefix") || null,
      nda_prefix: formData.get("nda_prefix") || null,
    };
    setBusy(button, true, "📦 Créer un scénario depuis le modèle");
    try {
      const data = await responseData(await fetch(`/scenarios/templates/${encodeURIComponent(workspace.dataset.templateKey)}/materialize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }));
      renderMaterialization(workspace, data);
      notify("Scénario matérialisé.", "success");
    } catch (error) {
      renderError(workspace, `Impossible de créer le scénario : ${error.message}`);
    } finally {
      setBusy(button, false, "📦 Créer un scénario depuis le modèle");
    }
  }

  async function play(workspace, form, button) {
    const dryRun = form.querySelector("[name='dry_run']")?.checked;
    if (!dryRun) {
      const confirm = window.PameliaUi?.confirm || ((options) => Promise.resolve(window.confirm(options.message)));
      const accepted = await confirm({
        title: "Émettre les messages du modèle",
        acceptLabel: "Émettre",
        variant: "danger",
        message: "La simulation est désactivée : les messages seront émis vers la destination sélectionnée.",
      });
      if (!accepted) return;
    }
    setBusy(button, true, "▶️ Exécuter le template");
    try {
      const data = await responseData(await fetch(`/scenarios/templates/${encodeURIComponent(workspace.dataset.templateKey)}/play`, {
        method: "POST",
        body: new FormData(form),
      }));
      renderPlay(workspace, data);
      notify(dryRun ? "Prévisualisation terminée." : "Exécution terminée.", "success");
    } catch (error) {
      renderError(workspace, `Impossible d’exécuter le modèle : ${error.message}`);
    } finally {
      setBusy(button, false, "▶️ Exécuter le template");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector("[data-scenario-template-workspace]");
    const form = workspace?.querySelector("[data-template-play-form]");
    if (!workspace || !form) return;
    const materializeButton = workspace.querySelector("[data-materialize-template]");
    materializeButton?.addEventListener("click", () => materialize(workspace, form, materializeButton));
    form.querySelector("[data-template-protocol]")?.addEventListener("change", () => refreshEndpointChoices(form));
    refreshEndpointChoices(form);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      play(workspace, form, event.submitter);
    });
  });
})();
