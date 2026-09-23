(() => {
  const type = document.getElementById("contact_type");
  const patient = document.getElementById("patient_id");
  const venue = document.getElementById("venue_id");
  if (!type || !patient || !venue) return;

  const updateAssociation = () => {
    const isPatient = type.value === "patient";
    patient.disabled = !isPatient;
    patient.required = isPatient;
    venue.disabled = isPatient;
    venue.required = !isPatient;
  };
  type.addEventListener("change", updateAssociation);
  updateAssociation();
})();
