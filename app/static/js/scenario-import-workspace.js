(() => {
  const form = document.getElementById("import-scenario-form");
  const button = document.getElementById("import-scenario-btn");
  if (!form || !button) return;

  const notify = (message, type = "info") => {
    if (window.toastSystem?.show) window.toastSystem.show(message, type);
    else console.info(message);
  };
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Import en cours…";
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
      notify("Scénario importé avec succès.", "success");
      window.setTimeout(() => window.location.assign("/scenarios"), 350);
    } catch (error) {
      notify(`Erreur lors de l’import du scénario : ${error.message}`, "error");
      button.disabled = false;
      button.textContent = originalText;
    }
  });
})();
