/* Comportements propres aux écrans de supervision des messages. */
(function () {
  "use strict";

  const notify = (message, kind = "info") => window.toastSystem?.show(message, kind);

  async function replayMessage(button) {
    const messageId = button.dataset.replayMessageId;
    if (!messageId) return;

    const confirmed = await window.PameliaUi.confirm({
      title: "Rejouer un message",
      message: "Rejouer le message #" + messageId + " vers son endpoint d’origine ?",
      acceptLabel: "Rejouer",
      variant: "danger",
    });
    if (!confirmed) return;

    const feedback = document.getElementById("replay-feedback");
    const initialLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Rejeu…";
    try {
      const { data } = await window.medbridgeHttp.request("/messages/" + messageId + "/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (data.status !== "success") throw new Error(data.message || "Le rejeu a échoué.");
      if (feedback) feedback.textContent = "Message " + messageId + " rejoué avec succès. Nouvel état : " + data.new_status + ".";
      window.location.reload();
    } catch (error) {
      const message = "Erreur lors du rejeu : " + (error.message || "erreur réseau.");
      if (feedback) feedback.textContent = message;
      notify(message, "error");
      button.disabled = false;
      button.textContent = initialLabel;
    }
  }

  function setupReplay() {
    document.querySelectorAll("[data-replay-message-id]").forEach((button) => {
      button.addEventListener("click", () => replayMessage(button));
    });
  }

  async function loadCotation(link) {
    const dossierId = link.dataset.dossierId;
    if (!dossierId) return;
    try {
      const { data } = await window.medbridgeHttp.get("/api/hprim/interventions/" + dossierId + "/cotations-count");
      if (!data.has_cotations || !data.cotations_count) return;

      link.classList.remove("hidden");
      const label = link.querySelector(".cotations-label");
      if (label) label.textContent = data.cotations_count === 1 ? "1 cotation" : data.cotations_count + " cotations";
    } catch (error) {
      console.warn("Impossible de charger les cotations du dossier " + dossierId + ".", error);
    }
  }

  async function loadCotations() {
    const links = Array.from(document.querySelectorAll(".cotations-link[data-dossier-id]")).filter(
      (link) => link.offsetParent !== null,
    );
    const workerCount = Math.min(4, links.length);
    let next = 0;
    const worker = async () => {
      while (next < links.length) {
        const link = links[next];
        next += 1;
        await loadCotation(link);
      }
    };
    await Promise.all(Array.from({ length: workerCount }, worker));
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupReplay();
    void loadCotations();
  });
})();
