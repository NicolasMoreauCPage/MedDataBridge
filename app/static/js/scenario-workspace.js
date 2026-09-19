/* Interactions du poste de travail Scénarios, sans gestionnaire inline. */
(function () {
  "use strict";

  const notify = (message, kind = "info") => {
    if (window.toastSystem?.show) window.toastSystem.show(message, kind === "warn" ? "warning" : kind);
  };

  async function configureTiming(workspace) {
    const scenarioId = workspace.dataset.scenarioId;
    if (!scenarioId) return;
    try {
      const { data: suggestion } = await window.medbridgeHttp.request(`/scenarios/${scenarioId}/suggest-realistic-timing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const analysis = suggestion.analysis || {};
      const config = suggestion.suggested_config || {};
      const confirmed = await window.PameliaUi.confirm({
        title: "Appliquer le timing réaliste",
        acceptLabel: "Appliquer",
        variant: "danger",
        message: [
          `Workflow détecté : ${analysis.detected_workflow || "non déterminé"}.`,
          analysis.workflow_description || "",
          `Événements : ${(analysis.event_sequence || []).join(" → ") || "non déterminés"}.`,
          `Ancrage : ${config.time_anchor_mode || "non déterminé"}; jitter : ${config.jitter_min_minutes ?? "?"}-${config.jitter_max_minutes ?? "?"} min.`,
          "La configuration temporelle actuelle sera remplacée.",
        ].filter(Boolean).join("\n\n"),
      });
      if (!confirmed) return;

      const { data: result } = await window.medbridgeHttp.request(`/scenarios/${scenarioId}/apply-realistic-timing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      notify(result.message || "Timing réaliste appliqué.", "success");
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      notify(`Impossible de configurer le timing : ${error.message}`, "error");
    }
  }

  function setupScenarioSend(workspace) {
    const form = workspace.querySelector("#send-scenario-form");
    const sendButton = workspace.querySelector("#send-scenario-btn");
    if (!form || !sendButton) return;

    form.addEventListener("submit", async (event) => {
      // La prévisualisation est une navigation normale : elle affiche son
      // rapport plutôt que de tenter d'interpréter une réponse HTML comme JSON.
      if (event.submitter?.name === "dry_run") return;
      event.preventDefault();
      const originalText = sendButton.textContent;
      sendButton.disabled = true;
      sendButton.textContent = "Envoi en cours…";
      try {
        const { response } = await window.medbridgeHttp.request(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (response.redirected) {
          window.location.assign(response.url);
          return;
        }
        notify("Scénario envoyé avec succès.", "success");
        window.setTimeout(() => window.location.reload(), 900);
      } catch (error) {
        notify(`Erreur lors de l’envoi : ${error.message}`, "error");
        sendButton.disabled = false;
        sendButton.textContent = originalText;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector("[data-scenario-workspace]");
    if (!workspace) return;
    workspace.querySelector("[data-realistic-timing]")?.addEventListener("click", () => configureTiming(workspace));
    setupScenarioSend(workspace);
  });
})();
