(() => {
  const dryRun = document.getElementById("dry-run");
  const runButton = document.getElementById("run-button");
  const runForm = document.getElementById("qualification-run-form");
  if (!dryRun || !runButton || !runForm) return;

  const updateRunMode = () => {
    runButton.textContent = dryRun.checked
      ? "Lancer la qualification à blanc"
      : "Émettre et qualifier";
    runButton.className = dryRun.checked
      ? "rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-800"
      : "rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-amber-700";
  };

  dryRun.addEventListener("change", updateRunMode);
  runForm.addEventListener("submit", async (event) => {
    if (dryRun.checked || runForm.dataset.confirmBypass === "true") {
      delete runForm.dataset.confirmBypass;
      return;
    }
    event.preventDefault();
    if (!window.PameliaUi?.confirm) {
      window.toastSystem?.show("Le dialogue de confirmation n'est pas disponible.", "error");
      return;
    }
    const confirmed = await window.PameliaUi.confirm({
      title: "Émettre et qualifier",
      message: "Cette exécution enverra un message au partenaire sélectionné. Continuer ?",
      acceptLabel: "Émettre",
      variant: "primary",
    });
    if (confirmed) {
      runForm.dataset.confirmBypass = "true";
      runForm.requestSubmit(event.submitter || undefined);
    }
  });

  updateRunMode();
})();
