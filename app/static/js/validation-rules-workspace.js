/* Édition et rechargement des règles de validation PAM/HPRIM. */
(function () {
  "use strict";

  const rulesArea = document.getElementById("rulesArea");
  const saveButton = document.getElementById("saveBtn");
  const reloadButton = document.getElementById("reloadBtn");
  const message = document.getElementById("msg");
  if (!rulesArea || !saveButton || !reloadButton || !message) return;

  let isDirty = false;

  function showStatus(text, type = "info") {
    const colors = {
      success: "text-emerald-700 dark:text-emerald-300",
      error: "text-red-700 dark:text-red-300",
      info: "text-slate-600 dark:text-slate-300",
    };
    message.textContent = text;
    message.className = `min-h-6 text-sm ${colors[type] || colors.info}`;
    window.toastSystem?.show?.(text, type);
  }

  function setBusy(button, busy, label) {
    button.disabled = busy;
    button.classList.toggle("opacity-60", busy);
    button.classList.toggle("cursor-wait", busy);
    button.textContent = busy ? "Traitement en cours…" : label;
  }

  async function saveRules() {
    let parsed;
    try {
      parsed = JSON.parse(rulesArea.value);
    } catch (error) {
      showStatus(`JSON invalide : ${error.message}`, "error");
      return;
    }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      showStatus("Les règles doivent être un objet JSON.", "error");
      return;
    }
    setBusy(saveButton, true, "Sauvegarder");
    try {
      const { data } = await window.medbridgeHttp.post("/api/validation-rules", parsed);
      isDirty = false;
      showStatus(data.message || "Règles sauvegardées.", "success");
    } catch (error) {
      showStatus(`Impossible de sauvegarder les règles : ${error.message}`, "error");
    } finally {
      setBusy(saveButton, false, "Sauvegarder");
    }
  }

  async function reloadRules() {
    if (isDirty) {
      if (!window.PameliaUi?.confirm) {
        showStatus("Le dialogue de confirmation n’est pas disponible.", "error");
        return;
      }
      const confirmed = await window.PameliaUi.confirm({
        title: "Recharger les règles",
        message: "Les modifications non sauvegardées seront perdues.",
        acceptLabel: "Recharger",
        variant: "danger",
      });
      if (!confirmed) return;
    }
    setBusy(reloadButton, true, "Recharger");
    try {
      const { data: rules } = await window.medbridgeHttp.get("/api/validation-rules");
      if (!rules || Array.isArray(rules) || typeof rules !== "object") {
        throw new Error("Format de règles invalide");
      }
      rulesArea.value = JSON.stringify(rules, null, 2);
      isDirty = false;
      showStatus("Règles rechargées.", "success");
    } catch (error) {
      showStatus(`Impossible de recharger les règles : ${error.message}`, "error");
    } finally {
      setBusy(reloadButton, false, "Recharger");
    }
  }

  rulesArea.addEventListener("input", () => { isDirty = true; });
  saveButton.addEventListener("click", () => { void saveRules(); });
  reloadButton.addEventListener("click", () => { void reloadRules(); });
})();
