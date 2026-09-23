(() => {
  "use strict";

  function updateSelectedCount() {
    const checkboxes = document.querySelectorAll(".scenario-checkbox:checked");
    const count = checkboxes.length;
    const endpointSelected = document.querySelector('input[name="endpoint_id"]:checked') !== null;

    document.getElementById("selectedScenarios").textContent = count;

    let totalMessages = 0;
    checkboxes.forEach((checkbox) => {
      const label = checkbox.closest("label");
      const match = label?.textContent.match(/\b(\d+)\s*msg\b/);
      if (match) {
        totalMessages += Number.parseInt(match[1], 10);
      }
    });

    const repeat = Number.parseInt(document.getElementById("repeatCount")?.value, 10) || 1;
    totalMessages *= repeat;

    document.getElementById("selectedMessages").textContent = totalMessages;
    const bottomMsgCount = document.getElementById("bottomMsgCount");
    if (bottomMsgCount) {
      bottomMsgCount.textContent = totalMessages || "0";
    }

    const topExecutionInfo = document.getElementById("topExecutionInfo");
    const bottomExecutionInfo = document.getElementById("bottomExecutionInfo");
    if (count > 0 && endpointSelected) {
      topExecutionInfo.textContent = `${count} scénario(s) sélectionné(s) - ${totalMessages} message(s)`;
      bottomExecutionInfo.innerHTML = `<strong id="bottomMsgCount">${totalMessages}</strong> message(s) seront envoyés`;
    } else if (count > 0) {
      topExecutionInfo.textContent = `${count} scénario(s) sélectionné(s) - Sélectionnez un endpoint`;
      bottomExecutionInfo.innerHTML = '<strong id="bottomMsgCount">0</strong> message(s) - Sélectionnez un endpoint';
    } else {
      topExecutionInfo.textContent = "Sélectionnez un endpoint et au moins 1 scénario";
      bottomExecutionInfo.innerHTML = '<strong id="bottomMsgCount">0</strong> message(s) seront envoyés';
    }

    const isReady = count > 0 && endpointSelected;
    [document.getElementById("topSubmitBtn"), document.getElementById("bottomSubmitBtn")].forEach((button) => {
      if (button) {
        button.disabled = !isReady;
        button.classList.toggle("opacity-50", !isReady);
      }
    });
  }

  function toggleAllScenarios() {
    const checkboxes = document.querySelectorAll(".scenario-checkbox");
    const allChecked = Array.from(checkboxes).every((checkbox) => checkbox.checked);
    checkboxes.forEach((checkbox) => {
      checkbox.checked = !allChecked;
    });
    updateSelectedCount();
  }

  function initializePage() {
    document.querySelectorAll('input[name="endpoint_id"]').forEach((radio) => {
      radio.addEventListener("change", updateSelectedCount);
    });
    document.querySelectorAll(".scenario-checkbox").forEach((checkbox) => {
      checkbox.addEventListener("change", updateSelectedCount);
    });
    document.getElementById("toggleAllScenariosBtn")?.addEventListener("click", toggleAllScenarios);
    document.getElementById("repeatCount")?.addEventListener("input", updateSelectedCount);
    updateSelectedCount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePage);
  } else {
    initializePage();
  }
})();
