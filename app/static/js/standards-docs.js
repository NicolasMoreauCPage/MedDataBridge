/* Modèles de messages de la documentation des standards. */
"use strict";

const templates = {
  "ADT^A01": `MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20251101000000||ADT^A01|MSG00001|P|2.5
EVN|A01|20251101000000|||APPLI^IHE
PID|||123456^^^HOPITAL||DUPONT^JEAN||19800101|M
PV1||I|CARDIO^101^1|||||||||||||||||1|||||||||||||||||||||||||20251101000000`,

  "ADT^A02": `MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20251101000000||ADT^A02|MSG00002|P|2.5
EVN|A02|20251101000000|||APPLI^IHE
PID|||123456^^^HOPITAL||DUPONT^JEAN||19800101|M
PV1||I|CARDIO^101^1|||||||||||||||||1|||||||||||||||||||||||||20251101000000|20251101120000`,

  "QBP^Q23": `MSH|^~\\&|SENDING_APP|SENDING_FAC|PIX_MGR|PIX_FAC|20251101000000||QBP^Q23^QBP_Q21|MSG00001|P|2.5
QPD|IHE PIX Query|QRY123|123456^^^HOPITAL
RCP|I`,

  "QBP^Q22": `MSH|^~\\&|SENDING_APP|SENDING_FAC|PDQ_MGR|PDQ_FAC|20251101000000||QBP^Q22^QBP_Q21|MSG00001|P|2.5
QPD|IHE PDQ Query|QRY123|@PID.5.1^DUPONT~@PID.5.2^JEAN~@PID.7^19800101
RCP|I`,

  "PIXm": {
    "resourceType": "Parameters",
    "parameter": [{
      "name": "sourceIdentifier",
      "valueIdentifier": {
        "system": "http://hopital-a.fr/id",
        "value": "123456"
      }
    }]
  },

  "Patient": {
    "resourceType": "Patient",
    "identifier": [{
      "system": "http://hopital.fr/id",
      "value": "123456"
    }],
    "name": [{
      "family": "DUPONT",
      "given": ["Jean"]
    }],
    "birthDate": "1980-01-01",
    "gender": "male"
  },

  "Encounter": {
    "resourceType": "Encounter",
    "status": "in-progress",
    "class": {
      "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
      "code": "IMP",
      "display": "inpatient encounter"
    },
    "subject": {
      "reference": "Patient/123"
    },
    "period": {
      "start": "2025-11-01T00:00:00+01:00"
    },
    "location": [{
      "location": {
        "reference": "Location/CARDIO-101"
      }
    }]
  }
};

const modal = document.getElementById("template-modal");
const titleEl = document.getElementById("templateTitle");
const contentEl = document.getElementById("templateContent");
const testLink = document.getElementById("testLink");
const copyBtn = document.getElementById("copyTemplate");

function determineEndpoint(type) {
  if (type.startsWith("ADT^") || type.startsWith("QBP^")) {
    return "/messages/send";
  }
  if (type === "PIXm") {
    return "/messages/send";
  }
  return "/messages/send";
}

function openTemplate(type, label) {
  const template = templates[type];
  if (!template) {
    contentEl.textContent = "// Template introuvable";
  } else if (typeof template === "string") {
    contentEl.textContent = template;
  } else {
    contentEl.textContent = JSON.stringify(template, null, 2);
  }
  titleEl.textContent = label;
  testLink.href = determineEndpoint(type);
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function closeModal() {
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

document.querySelectorAll("[data-template]").forEach((button) => {
  button.addEventListener("click", () => {
    const type = button.dataset.template;
    const label = button.dataset.label || type;
    openTemplate(type, label);
  });
});

document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", closeModal);
});

copyBtn.addEventListener("click", () => {
  const text = contentEl.textContent || "";
  navigator.clipboard.writeText(text).then(() => {
    copyBtn.classList.add("bg-green-600");
    copyBtn.textContent = "Copié !";
    setTimeout(() => {
      copyBtn.classList.remove("bg-green-600");
      copyBtn.textContent = "Copier";
    }, 1600);
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !modal.classList.contains("hidden")) {
    closeModal();
  }
});
