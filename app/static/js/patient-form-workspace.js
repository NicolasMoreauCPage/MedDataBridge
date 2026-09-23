/* Interactions du formulaire patient : sections repliables et identité exemple. */
(function () {
  "use strict";

  function animateDetails(details) {
    const summary = details.querySelector("summary");
    const content = details.querySelector("summary + div");
    if (!summary || !content) return;

    summary.addEventListener("click", (event) => {
      event.preventDefault();
      if (details.open) {
        content.style.height = `${content.offsetHeight}px`;
        content.style.overflow = "hidden";
        requestAnimationFrame(() => {
          content.style.transition = "height 0.3s ease-out, opacity 0.3s ease-out";
          content.style.height = "0px";
          content.style.opacity = "0";
        });
        window.setTimeout(() => {
          details.removeAttribute("open");
          content.style.height = "";
          content.style.overflow = "";
          content.style.opacity = "";
          content.style.transition = "";
        }, 300);
        return;
      }

      details.setAttribute("open", "");
      content.style.overflow = "hidden";
      content.style.height = "0px";
      content.style.opacity = "0";
      requestAnimationFrame(() => {
        content.style.transition = "height 0.3s ease-out, opacity 0.3s ease-out";
        content.style.height = `${content.scrollHeight}px`;
        content.style.opacity = "1";
      });
      window.setTimeout(() => {
        content.style.height = "";
        content.style.overflow = "";
        content.style.transition = "";
      }, 300);
    });
  }

  function initPatientSample() {
    const form = document.querySelector("form[data-patient-form]");
    const regenerateButton = document.getElementById("regenerate-sample");
    if (!form || !regenerateButton) return;

    const status = document.getElementById("sample-status");
    const defaultLabel = regenerateButton.textContent;
    const fieldNames = [
      "prefix", "family", "given", "middle", "suffix", "birth_family",
      "birth_date", "gender", "address", "city", "state", "postal_code",
      "country", "phone", "mobile", "work_phone", "email", "birth_address",
      "birth_city", "birth_state", "birth_postal_code", "birth_country",
      "nir", "marital_status", "nationality", "identity_reliability_code",
      "mothers_maiden_name", "primary_care_provider",
    ];

    function setStatus(message, kind) {
      if (!status) return;
      status.textContent = message;
      status.classList.toggle("text-emerald-200", kind === "success");
      status.classList.toggle("text-rose-200", kind === "error");
    }

    function applyValues(data) {
      fieldNames.forEach((name) => {
        const input = form.querySelector(`[name="${name}"]`);
        if (!input) return;
        let value = data[name] || "";
        if (input instanceof HTMLInputElement && input.type === "date" && value) {
          value = String(value).slice(0, 10);
        }
        input.value = value;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }

    regenerateButton.addEventListener("click", async () => {
      regenerateButton.disabled = true;
      regenerateButton.textContent = "Chargement…";
      try {
        const { data: payload } = await window.medbridgeHttp.get("/patients/sample-identity");
        applyValues(payload.sample_data || payload);
        setStatus("Nouvelle identité appliquée", "success");
      } catch (error) {
        console.error(error);
        setStatus("Impossible de générer une identité", "error");
      } finally {
        regenerateButton.disabled = false;
        regenerateButton.textContent = defaultLabel;
      }
    });
  }

  function init() {
    document.querySelectorAll("details").forEach(animateDetails);
    initPatientSample();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
