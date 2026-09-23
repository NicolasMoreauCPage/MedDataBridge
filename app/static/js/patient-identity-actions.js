(() => {
  const changeForm = document.querySelector("[data-patient-identifier-change]");
  if (changeForm) {
    const input = document.getElementById("new_value");
    const error = document.getElementById("identifier-change-error");
    const submit = changeForm.querySelector("button[type='submit']");
    const validate = () => {
      const unchanged = input.value.trim() !== "" && input.value.trim() === input.dataset.currentValue.trim();
      error.classList.toggle("hidden", !unchanged);
      submit.disabled = unchanged;
      submit.classList.toggle("opacity-50", unchanged);
      submit.classList.toggle("cursor-not-allowed", unchanged);
      input.setAttribute("aria-invalid", String(unchanged));
    };
    input.addEventListener("input", validate);
  }

  const mergeForm = document.querySelector("[data-patient-merge]");
  if (!mergeForm) return;
  const source = document.getElementById("source_patient_id");
  const survivor = document.getElementById("surviving_patient_id");
  const preview = document.getElementById("merge-mrg-preview");
  const sourceIdentifier = document.getElementById("merge-source-identifier");
  const error = document.getElementById("merge-selection-error");
  const submit = mergeForm.querySelector("button[type='submit']");
  const refresh = () => {
    const hasBoth = Boolean(source.value && survivor.value);
    const samePatient = hasBoth && source.value === survivor.value;
    sourceIdentifier.textContent = source.options[source.selectedIndex]?.dataset.identifier || "";
    preview.classList.toggle("hidden", !hasBoth || samePatient);
    error.classList.toggle("hidden", !samePatient);
    submit.disabled = samePatient;
    submit.classList.toggle("opacity-50", samePatient);
    submit.classList.toggle("cursor-not-allowed", samePatient);
    source.setAttribute("aria-invalid", String(samePatient));
    survivor.setAttribute("aria-invalid", String(samePatient));
  };
  source.addEventListener("change", refresh);
  survivor.addEventListener("change", refresh);
  refresh();
})();
