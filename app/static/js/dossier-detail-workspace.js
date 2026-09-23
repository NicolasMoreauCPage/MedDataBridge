(() => {
  const workspace = document.querySelector("[data-dossier-detail]");
  if (!workspace?.dataset.dossierId) return;

  const loadCotationsCount = async () => {
    try {
      const { data } = await window.medbridgeHttp.get(
        `/api/hprim/interventions/${encodeURIComponent(workspace.dataset.dossierId)}/cotations-count`,
      );
      if (!data.has_cotations || data.cotations_count < 1) return;

      const button = document.getElementById("view-cotations-btn");
      const badge = document.getElementById("cotations-badge");
      const label = document.getElementById("cotations-label");
      if (!button || !badge || !label) return;

      button.classList.remove("hidden");
      badge.textContent = data.cotations_count;
      label.textContent = data.cotations_count === 1
        ? "Voir la cotation"
        : `Voir les ${data.cotations_count} cotations`;
    } catch (error) {
      console.warn("Erreur lors du chargement du nombre de cotations:", error);
    }
  };

  loadCotationsCount();
})();
