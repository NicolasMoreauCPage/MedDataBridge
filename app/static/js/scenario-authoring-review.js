/* Rafraîchit les erreurs de préparation sans navigation. */
(function () {
  "use strict";
  function issueElement(issue) {
    const item = document.createElement("li");
    const error = issue.level === "error";
    item.className = `rounded-lg border p-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/30 dark:text-red-100" : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"}`;
    item.textContent = `${error ? "À corriger" : "À vérifier"} — ${issue.message}`;
    return item;
  }
  document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-scenario-authoring-review]");
    const button = root?.querySelector("[data-refresh-validation]");
    const list = root?.querySelector("[data-authoring-issues]");
    if (!root || !button || !list || !window.medbridgeHttp) return;
    button.addEventListener("click", async () => {
      button.disabled = true; button.textContent = "Vérification…";
      try {
        const { data } = await window.medbridgeHttp.post(`/scenarios/${root.dataset.scenarioId}/authoring/validate`, {});
        list.replaceChildren();
        if (data.issues.length) data.issues.forEach((issue) => list.append(issueElement(issue)));
        else { const ok = document.createElement("li"); ok.className = "rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100"; ok.textContent = "Le scénario est prêt à être activé."; list.append(ok); }
        window.toastSystem?.show?.(data.valid ? "Scénario prêt." : "Des corrections sont nécessaires.", data.valid ? "success" : "warning");
      } catch (error) { window.toastSystem?.show?.(`Impossible de vérifier le scénario : ${error.message}`, "error"); }
      finally { button.disabled = false; button.textContent = "Actualiser la vérification"; }
    });
  });
})();
