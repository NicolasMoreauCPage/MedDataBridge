(() => {
  const workspace = document.querySelector("[data-dossier-type-change]");
  const form = document.getElementById("changeTypeForm");
  const typeSelect = document.getElementById("newType");
  const forceButton = document.getElementById("forceChange");
  const warningArea = document.getElementById("warningArea");
  const warningMessages = document.getElementById("warningMessages");
  const successArea = document.getElementById("successArea");
  if (!workspace?.dataset.dossierId || !form || !typeSelect || !forceButton) return;

  let pendingType = "";
  const endpoint = (force = false) => {
    const params = new URLSearchParams({ new_type: pendingType });
    if (force) params.set("force", "true");
    return `/dossier-type/${encodeURIComponent(workspace.dataset.dossierId)}/change?${params}`;
  };
  const showSuccess = () => {
    warningArea.classList.add("hidden");
    successArea.classList.remove("hidden");
    window.setTimeout(() => {
      window.location.assign(`/dossiers/${encodeURIComponent(workspace.dataset.dossierId)}`);
    }, 2000);
  };
  const submitChange = async (force = false) => {
    forceButton.disabled = true;
    try {
      const { data } = await window.medbridgeHttp.request(endpoint(force), { method: "POST" });
      if (data.status === "success") {
        showSuccess();
        return;
      }
      warningMessages.replaceChildren();
      (data.warnings || []).forEach((warning) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = warning;
        warningMessages.append(paragraph);
      });
      warningArea.classList.remove("hidden");
    } catch (error) {
      window.toastSystem?.show(error.message || "Le changement de type a échoué.", "error");
    } finally {
      forceButton.disabled = false;
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    pendingType = typeSelect.value;
    submitChange();
  });
  forceButton.addEventListener("click", () => submitChange(true));
})();
