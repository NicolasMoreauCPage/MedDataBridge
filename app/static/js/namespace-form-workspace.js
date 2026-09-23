(() => {
  const systemInput = document.getElementById("system") || document.getElementById("systemInput");
  const oidInput = document.getElementById("oid") || document.getElementById("oidInput");

  const extractOid = () => {
    const value = systemInput.value.trim();
    const oid = value.startsWith("urn:oid:") ? value.slice(8) : "";
    oidInput.value = oid;
    if (oidInput.id === "oid") {
      oidInput.placeholder = oid || "Sera extrait automatiquement de l'URI";
    }
  };
  if (systemInput && oidInput) {
    systemInput.addEventListener("input", extractOid);
    systemInput.addEventListener("change", extractOid);
    extractOid();
  }

  const prefixMode = document.getElementById("prefix_mode");
  const patternField = document.getElementById("pattern_field");
  const rangeFields = document.getElementById("range_fields");
  if (!prefixMode || !patternField || !rangeFields) return;

  const togglePrefixMode = () => {
    const range = prefixMode.value === "range";
    patternField.hidden = range;
    rangeFields.hidden = !range;
  };
  prefixMode.addEventListener("change", togglePrefixMode);
  togglePrefixMode();
})();
