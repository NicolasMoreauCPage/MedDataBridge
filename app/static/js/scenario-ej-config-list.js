(() => {
  "use strict";

  const notify = (message, type = "info") => {
    if (window.toastSystem?.show) {
      window.toastSystem.show(message, type);
      return;
    }
    console.info(message);
  };

  async function deleteConfig(button) {
    const { ejId, ejName } = button.dataset;
    if (!ejId) return;
    if (!window.PameliaUi?.confirm) {
      notify("Le dialogue de confirmation n'est pas disponible.", "error");
      return;
    }

    const confirmed = await window.PameliaUi.confirm({
      title: "Supprimer la configuration",
      message: `Êtes-vous sûr de vouloir supprimer la configuration de « ${ejName} » ?`,
      acceptLabel: "Supprimer",
      variant: "danger",
    });
    if (!confirmed) return;

    button.disabled = true;
    try {
      await window.medbridgeHttp.request(`/config/scenario-ej/${encodeURIComponent(ejId)}`, {
        method: "DELETE",
      });
      notify("Configuration supprimée.", "success");
      window.setTimeout(() => window.location.reload(), 350);
    } catch (error) {
      notify(`Erreur : ${error.message}`, "error");
      button.disabled = false;
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-scenario-ej-config]");
    if (button) deleteConfig(button);
  });
})();
