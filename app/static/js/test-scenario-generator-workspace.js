(() => {
  const form = document.getElementById("scenario-form");
  const result = document.getElementById("scenario-result");
  const feedback = document.getElementById("scenario-feedback");
  const messagesContainer = document.getElementById("scenario-messages");
  if (!form || !result || !feedback || !messagesContainer) return;

  let generatedMessages = [];
  let generatedId = "scenario";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    feedback.classList.add("hidden");
    try {
      const { data: payload } = await window.medbridgeHttp.post("/test-scenario-generator/generate", {
        scenario_type: document.getElementById("scenario-type").value,
        specialty: document.getElementById("specialty").value || null,
        patient_count: Number(document.getElementById("patient-count").value),
        error_injections: document.getElementById("inject-invalid-date").checked
          ? [{ error_type: "invalid_field", probability: 1 }]
          : [],
      });
      result.classList.remove("hidden");
      document.getElementById("scenario-name").textContent = payload.name;
      document.getElementById("scenario-description").textContent = payload.description;
      generatedMessages = payload.messages_hl7 || [];
      generatedId = payload.id || "scenario";
      messagesContainer.replaceChildren();
      generatedMessages.forEach((message, index) => {
        const details = document.createElement("details");
        details.className = "rounded-lg border border-slate-200 dark:border-slate-700";
        details.open = index === 0;
        const summary = document.createElement("summary");
        summary.className = "cursor-pointer px-3 py-2 font-semibold";
        summary.textContent = `Message ${index + 1} · ${(message.match(/MSH\|[^\r]*\|ADT\^([^|]+)/) || [])[1] || "HL7"}`;
        const pre = document.createElement("pre");
        pre.className = "overflow-x-auto border-t border-slate-200 bg-slate-950 p-3 text-xs text-emerald-300";
        pre.textContent = message.replaceAll("\r", "\n");
        details.append(summary, pre);
        messagesContainer.append(details);
      });
      feedback.textContent = "Scénario généré localement. Aucun message n’a été envoyé.";
      feedback.className = "rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800";
    } catch (error) {
      result.classList.add("hidden");
      feedback.textContent = error.message || "La génération a échoué.";
      feedback.className = "rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800";
    }
    feedback.classList.remove("hidden");
  });

  document.getElementById("copy-scenario").addEventListener("click", () => {
    navigator.clipboard.writeText(generatedMessages.join("\r"));
  });
  document.getElementById("download-scenario").addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([generatedMessages.join("\r")], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${generatedId}.hl7`;
    link.click();
    URL.revokeObjectURL(url);
  });
})();
