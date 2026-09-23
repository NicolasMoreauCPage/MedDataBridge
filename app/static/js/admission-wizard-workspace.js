(() => {
  const serviceSelect = document.getElementById("service_id");
  const ufSelect = document.getElementById("uf_id");
  const bedSelector = document.getElementById("lit_selector");
  const bedInput = document.getElementById("lit_id");

  if (!serviceSelect || !ufSelect || !bedSelector || !bedInput) return;

  const showBedStatus = (message, tone = "text-slate-500") => {
    bedSelector.replaceChildren();
    const status = document.createElement("div");
    status.className = `col-span-3 ${tone} text-sm py-8 text-center`;
    status.textContent = message;
    bedSelector.append(status);
  };

  const resetUf = (label) => {
    ufSelect.replaceChildren(new Option(label, ""));
    bedInput.value = "";
  };

  serviceSelect.addEventListener("change", async () => {
    const serviceId = serviceSelect.value;
    resetUf(serviceId ? "Chargement des UF…" : "-- Sélectionner une UF --");
    showBedStatus(serviceId ? "Chargement des unités fonctionnelles…" : "Sélectionnez un service");
    if (!serviceId) return;

    ufSelect.disabled = true;
    try {
      const { data: ufs } = await window.medbridgeHttp.get(
        `/wizard/api/services/${encodeURIComponent(serviceId)}/ufs`,
      );
      resetUf("-- Sélectionner une UF --");
      ufs.forEach((uf) => ufSelect.add(new Option(uf.name, uf.id)));
      showBedStatus(ufs.length ? "Sélectionnez une UF" : "Aucune UF disponible", ufs.length ? "text-slate-500" : "text-amber-700");
    } catch (error) {
      console.error("Erreur lors du chargement des UF:", error);
      resetUf("Chargement impossible");
      showBedStatus("Impossible de charger les unités fonctionnelles.", "text-red-700");
    } finally {
      ufSelect.disabled = false;
    }
  });

  ufSelect.addEventListener("change", async () => {
    const ufId = ufSelect.value;
    bedInput.value = "";
    showBedStatus(ufId ? "Recherche des lits disponibles…" : "Sélectionnez une UF");
    if (!ufId) return;

    try {
      const { data: beds } = await window.medbridgeHttp.get(
        `/wizard/api/ufs/${encodeURIComponent(ufId)}/lits?status=free`,
      );
      bedSelector.replaceChildren();
      if (!beds.length) {
        showBedStatus("Aucun lit disponible dans cette UF", "text-amber-700");
        return;
      }
      beds.forEach((bed) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "lit-button p-4 border-2 border-green-300 bg-green-50 rounded-xl hover:bg-green-100 hover:border-green-600 transition-all cursor-pointer text-center";
        button.dataset.litId = bed.id;
        button.setAttribute("aria-pressed", "false");
        const name = document.createElement("div");
        name.className = "font-bold text-lg text-green-700";
        name.textContent = bed.name;
        const availability = document.createElement("div");
        availability.className = "text-xs text-green-600";
        availability.textContent = "Disponible";
        button.append(name, availability);
        bedSelector.append(button);
      });
    } catch (error) {
      console.error("Erreur lors du chargement des lits:", error);
      showBedStatus("Impossible de charger les lits disponibles.", "text-red-700");
    }
  });

  bedSelector.addEventListener("click", (event) => {
    const selected = event.target.closest(".lit-button");
    if (!selected) return;
    bedSelector.querySelectorAll(".lit-button").forEach((button) => {
      const active = button === selected;
      button.classList.toggle("ring-2", active);
      button.classList.toggle("ring-blue-500", active);
      button.classList.toggle("bg-blue-50", active);
      button.classList.toggle("border-blue-600", active);
      button.classList.toggle("border-green-300", !active);
      button.classList.toggle("bg-green-50", !active);
      button.setAttribute("aria-pressed", String(active));
    });
    bedInput.value = selected.dataset.litId;
  });
})();
