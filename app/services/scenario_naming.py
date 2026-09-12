"""Présentation cohérente des noms de scénarios importés.

Les catalogues historiques CPage utilisent des noms de fichiers et de classes
Java (camelCase, abréviations, ``.txt``). Les clés restent techniques et
stables ; seul le libellé visible par un opérateur est normalisé ici.
"""

from __future__ import annotations

import re


_EXACT_NAMES = {
    "1ertestcreationippetdossierdk": "Premier test de création d’IPP et de dossier DK",
    "correctionchangementstatutextvershospit": "Correction de changement de statut externe vers hospitalisation",
    "changementstatuteversh": "Changement de statut externe vers hospitalisation",
    "correctionstatutuversh": "Correction de changement de statut d’urgence vers hospitalisation",
    "preadcorrectionstatuteversh": "Pré-admission : correction de changement de statut externe vers hospitalisation",
    "preadcorrectionstatuthverse": "Pré-admission : correction de changement de statut hospitalisation vers externe",
    "preadcorrectionstatuthversseance": "Pré-admission : correction de changement de statut hospitalisation vers séance",
    "preadcorrectionstatuthversurg": "Pré-admission : correction de changement de statut hospitalisation vers urgence",
    "preadcorrectionstatuturgverse": "Pré-admission : correction de changement de statut urgence vers externe",
}

# Libellés PAM compacts issus de l'ancien outil. Ils ne peuvent pas être
# correctement segmentés de façon automatique (p. ex. ``UFRespEtLoc``).
_EXACT_NAMES.update({
    "msga01": "Message A01",
    "2hospitjourlememejour": "Deux hospitalisations de jour le même jour",
    "ehpadsortietransfertretourtransfert": "EHPAD : sortie, transfert et retour de transfert",
    "insertupdatecl": "Insertion et mise à jour de CL",
    "testentreeurgencesortiedeces": "Entrée aux urgences, sortie et décès",
    "changementlitsuiviparchangementinutile": "Changement de lit suivi d’un changement sans effet",
    "changementlitsuiviparchangementufloc": "Changement de lit suivi d’un changement d’UF de localisation",
    "changementlitsuiviparchangementufresp": "Changement de lit suivi d’un changement d’UF responsable",
    "changementlitsuiviparchangementufrespetloc": "Changement de lit suivi d’un changement d’UF responsable et de localisation",
    "changementstatutbbsuiviparchangementinutile": "Changement de statut du bébé suivi d’un changement sans effet",
    "changementstatutbbsuiviparchangementlit": "Changement de statut du bébé suivi d’un changement de lit",
    "changementstatutbbsuiviparchangementufloc": "Changement de statut du bébé suivi d’un changement d’UF de localisation",
    "changementstatutbbsuiviparchangementufresp": "Changement de statut du bébé suivi d’un changement d’UF responsable",
    "changementstatutbbsuiviparchangementufrespetloc": "Changement de statut du bébé suivi d’un changement d’UF responsable et de localisation",
    "doublechangementresponsabilite": "Double changement de responsabilité",
    "externeajoutmedecintraitant": "Externe : ajout d’un médecin traitant",
    "hospitadmissionsimpledxcare": "Hospitalisation : admission simple DxCare",
    "hospitentreesouscontraintepolice": "Hospitalisation : entrée sous contrainte policière",
    "hospitjourmedecintraitant": "Hospitalisation de jour avec médecin traitant",
    "hospitsimpleidentexterne": "Hospitalisation simple avec identifiant externe",
    "hospitsimplecora": "Hospitalisation simple CORA",
    "hospitpreadmission": "Hospitalisation avec pré-admission",
    "identitecreationhommemarie": "Identité : création d’un homme marié",
    "identitecreationhommemarieavecnomusuelnaissance": "Identité : homme marié avec nom usuel et nom de naissance",
    "identitecreationmarieemodificationdivorcee": "Identité : création mariée puis modification divorcée",
    "identitecreationmodif": "Identité : création et modification",
    "identitecreationmodifdeces": "Identité : création, modification et décès",
    "identitecreationmodifsuppradresse": "Identité : création, modification et suppression d’adresse",
    "identitecreationpatientetranger": "Identité : création d’un patient étranger",
    "identitedisplaylegalname": "Identité : affichage du nom légal",
    "identite7prenomsdenaissance": "Identité : sept prénoms de naissance",
    "identiteajoutplacementpsyiti30": "Identité : ajout d’un placement en psychiatrie (ITI-30)",
    "identitecreationmodifcristal": "Identité : création et modification Cristal",
    "identitefusionavecdossierexterne": "Identité : fusion avec dossier externe",
    "identitenomprenom": "Identité : nom et prénom",
    "materniteneonatsortiebbapresmaman": "Maternité : sortie du nouveau-né après la mère",
    "maternitesimpledxcareobx": "Maternité simple DxCare avec OBX",
    "mutationcorrigeenchangementloc": "Mutation corrigée par changement de localisation",
    "mutationsuiviparchangementtarif": "Mutation suivie d’un changement de tarif",
    "personneaprevenircristal": "Personne à prévenir Cristal",
    "seancesavecclotureadministrative": "Séances avec clôture administrative",
    "sortieretourpermission": "Sortie et retour de permission",
    "sortieretourtransfert": "Sortie, retour et transfert",
    "urgencemiseenlita02correctioninutile": "Urgence : mise en lit A02, correction sans effet",
    "urgencemiseenlita02correctionloca02": "Urgence : mise en lit A02, correction de localisation A02",
    "urgencemiseenlita02correctionlocresp": "Urgence : mise en lit A02, correction de localisation responsable",
    "urgencemiseenlita02correctionrespa02": "Urgence : mise en lit A02, correction de responsabilité A02",
    "urgencemodificationchgtstatut": "Urgence : modification de changement de statut",
    "urgenceprovinsmodifadm": "Urgence Provins : modification d’admission",
    "venueconfidentielle": "Venue confidentielle",
    "entreesortietransfert": "Entrée, sortie et transfert",
    "entreetransfertinterneavecpread": "Entrée et transfert interne avec pré-admission",
    "hospitcariatidesmodeentree8": "Hospitalisation Cariatides : mode d’entrée 8",
    "hospitchangementrespcr": "Hospitalisation : changement de responsable CR",
    "hospitcomplexe": "Hospitalisation complexe",
    "hospitjour": "Hospitalisation de jour",
    "hospitnumeroarchive": "Hospitalisation avec numéro d’archive",
    "hospitparcoursmoins16ans": "Hospitalisation : parcours de moins de 16 ans",
    "hospitpsycariatides": "Hospitalisation psychiatrique Cariatides",
    "hospitpsysillage": "Hospitalisation psychiatrique Sillage",
    "hospitsimple": "Hospitalisation simple",
    "hospitsimplesillage": "Hospitalisation simple Sillage",
    "hospitsimplesillageufresplocdifferentes": "Hospitalisation simple Sillage : UF responsable et localisation différentes",
    "hospitverifmodeentree": "Hospitalisation : vérification du mode d’entrée",
    "hospitannulvenue": "Hospitalisation : annulation de venue",
    "materniteneonat": "Maternité et néonatologie",
    "identitepersonneenrelation": "Identité : personne en relation",
    "mouvementpersonneaprevenir": "Mouvement de personne à prévenir",
    "testihescenario3": "Test de scénario IHE 3",
    "hospitsimpleconsentement": "Hospitalisation simple avec consentement",
    "hospitsimplepmsiurgence": "Hospitalisation simple PMSI avec urgence",
    "placementpsya31": "Placement en psychiatrie A31",
    "preadsuppread": "Pré-admission : suppression de pré-admission",
    "rattachementdossier": "Rattachement de dossier",
    "sortiecontreavismedical": "Sortie contre avis médical",
    "sortiefuguesansretour": "Sortie en fugue sans retour",
    "sortieretourfugue": "Sortie et retour de fugue",
    "urgencesillage": "Urgence Sillage",
    "urgencesillagehavre": "Urgence Sillage Le Havre",
    "urgencesillagehavre2": "Urgence Sillage Le Havre 2",
    "siucreateannulation": "SIU : création et annulation de rendez-vous",
    "siucreatemodif": "SIU : création et modification de rendez-vous",
    "siucreationavecmail": "SIU : création de rendez-vous avec courriel",
    "siucreationrdvavecpersonneresponsablerdv": "SIU : rendez-vous avec personne responsable",
    "comparegenere": "Comparaison générée",
    "mllpehospitsimple": "MLLP : externe vers hospitalisation simple",
})

_COMPOUND_REPLACEMENTS = (
    ("changementstatut", "changement statut"),
    ("creationacte", "creation acte"),
    ("modificationacte", "modification acte"),
    ("suppressionacte", "suppression acte"),
    ("creationdossier", "creation dossier"),
    ("suppressiondossier", "suppression dossier"),
    ("creationidentite", "creation identite"),
    ("creationucd", "creation ucd"),
    ("creationmvt", "creation mouvement"),
    ("inser tmvt", "insert mouvement"),
    ("insertmvt", "insert mouvement"),
    ("chgtstatut", "changement statut"),
    ("modifadm", "modification admission"),
    ("modifperm", "modification permission"),
    ("medecintraitant", "medecin traitant"),
    ("medecinexecutant", "medecin executant"),
    ("medecinprescripteur", "medecin prescripteur"),
    ("nouvelleintervention", "nouvelle intervention"),
    ("interventionexistante", "intervention existante"),
    ("dossierexterne", "dossier externe"),
    ("horsvenue", "hors venue"),
    ("sansmedecin", "sans medecin"),
    ("sansuf", "sans uf"),
    ("codeassociation", "code association"),
    ("codeindication", "code indication"),
    ("entprealable", "entente prealable"),
    ("grosfichier", "gros fichier"),
    ("multivenue", "multi venue"),
    ("rejetprovins", "rejet provins"),
    ("personneaprevenir", "personne a prevenir"),
    ("retourb2", "retour b2"),
    ("sortieretour", "sortie retour"),
    ("entreesortietransfert", "entree sortie transfert"),
    ("entreetransfert", "entree transfert"),
    ("sortiecontreavis", "sortie contre avis"),
    ("sortiefugue", "sortie fugue"),
    ("urgencesillage", "urgence sillage"),
    ("materniteneonat", "maternite neonat"),
    ("hospitsimple", "hospitalisation simple"),
    ("hospitjour", "hospitalisation de jour"),
    ("hospitnuit", "hospitalisation de nuit"),
    ("hospitpsy", "hospitalisation psychiatrie"),
    ("hospit", "hospitalisation"),
    ("pread", "pre admission"),
    ("urgence", "urgence"),
)

_WORDS = {
    "acte": "acte", "admission": "admission", "annul": "annulation",
    "annulation": "annulation", "avec": "avec", "b2": "B2", "bb": "bébé",
    "cas": "cas", "cariatides": "Cariatides", "ccam": "CCAM", "changement": "changement",
    "cl": "CL", "cloture": "clôture", "code": "code", "coeffnull": "coefficient nul",
    "consentement": "consentement", "cora": "CORA", "correction": "correction",
    "cr": "CR", "cristalnet": "CristalNet", "cst": "CST", "creation": "création",
    "deces": "décès", "dk": "DK", "dmu": "DMU", "dossier": "dossier",
    "dxcare": "DxCare", "dxlab": "DxLab", "e": "externe", "eh": "externe hospitalisation",
    "ehpad": "EHPAD", "en": "en", "entente": "entente", "entree": "entrée",
    "et": "et", "existant": "existant", "externe": "externe", "facturable": "facturable",
    "fugue": "fugue", "fu": "fonctionnelle", "groupe": "groupe", "ha4": "HA4",
    "ha20": "HA20", "havre": "Havre", "h": "hospitalisation", "hl7": "HL7",
    "homme": "homme", "hospitalisation": "hospitalisation", "identexterne": "identifiant externe",
    "identite": "identité", "ihe": "IHE", "inexistant": "inexistant", "inlog": "INLOG",
    "insert": "insertion", "intermediaire": "intermédiaire", "interne": "interne",
    "intervention": "intervention", "ipp": "IPP", "jour": "jour", "legal": "légal",
    "lememejour": "le même jour", "letis": "LETIS", "liberal": "libéral", "lit": "lit",
    "loc": "localisation", "localisation": "localisation", "maman": "maman", "marie": "marié",
    "maternite": "maternité", "medecin": "médecin", "meme": "même", "mise": "mise",
    "mixte": "mixte", "mllp": "MLLP", "mode": "mode", "modif": "modification",
    "modification": "modification", "molis": "MOLIS", "mouvement": "mouvement", "mt": "médecin traitant",
    "mut": "mutation", "mutation": "mutation", "nabm": "NABM", "naissance": "naissance",
    "neonat": "néonatologie", "nf": "NF", "ngap": "NGAP", "nom": "nom", "non": "non",
    "nouvelle": "nouvelle", "numero": "numéro", "obx": "OBX", "par": "par", "parcours": "parcours",
    "patient": "patient", "pmsi": "PMSI", "police": "police", "preadmission": "pré-admission",
    "pre": "pré", "premier": "premier", "prenom": "prénom", "prescripteur": "prescripteur",
    "provins": "Provins", "psy": "psychiatrie", "quimp": "QUIMP", "rattachement": "rattachement",
    "rdv": "rendez-vous", "relation": "relation", "resp": "responsable", "responsabilite": "responsabilité",
    "retour": "retour", "s12": "S12", "sans": "sans", "seance": "séance", "seances": "séances",
    "sillage": "Sillage", "siu": "SIU", "soins": "soins", "sortie": "sortie", "statut": "statut",
    "suppr": "suppression", "suppression": "suppression", "sur": "sur", "tarif": "tarif",
    "test": "test", "traitant": "traitant", "transfert": "transfert", "u": "urgence",
    "ucd": "UCD", "uf": "UF", "ufloc": "UF de localisation", "ufresp": "UF responsable",
    "urgence": "urgence", "venue": "venue", "vers": "vers", "webcad": "WEBCAD", "xplore": "XPLORE",
    "yyyy011": "YYYY011",
}

_PHRASES = (
    ("changement statut", "changement de statut"),
    ("creation acte", "création d’acte"),
    ("modification acte", "modification d’acte"),
    ("suppression acte", "suppression d’acte"),
    ("creation dossier", "création de dossier"),
    ("suppression dossier", "suppression de dossier"),
    ("creation identite", "création d’identité"),
    ("creation ucd", "création de médicament UCD"),
    ("ajout acte", "ajout d’acte"),
    ("ajout medicament", "ajout de médicament"),
    ("hospitalisation de jour le meme jour", "hospitalisation de jour le même jour"),
    ("pre admission", "pré-admission"),
    ("a prevenir", "à prévenir"),
    ("contre avis medical", "contre avis médical"),
    ("sans medecin", "sans médecin"),
    ("sans uf", "sans UF"),
    ("uf resp", "UF responsable"),
    ("uf loc", "UF de localisation"),
)


def humanize_scenario_name(name: str | None, *, family: str | None = None) -> str:
    """Return a French operator-facing name without changing the technical key.

    ``family`` may be ``pam`` or ``hprim`` when the source label itself has no
    protocol prefix (which is the case for historical HPRIM file names).
    """
    raw = (name or "").strip()
    if not raw:
        return "Scénario sans nom"

    if family in {"pam", "hprim"} and not raw.lower().startswith(("ihe pam", "hprim")):
        raw = f"{'IHE PAM' if family == 'pam' else 'HPRIM'} - {raw}"

    prefix = ""
    if raw.lower().startswith("ihe pam -"):
        prefix, raw = "IHE PAM – ", raw.split("-", 1)[1].strip()
    elif raw.lower().startswith("hprim -"):
        prefix, raw = "HPRIM – ", raw.split("-", 1)[1].strip()

    raw = re.sub(r"\.(?:txt|xml|hl7)$", "", raw, flags=re.IGNORECASE)
    exact_key = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if exact_key in _EXACT_NAMES:
        return prefix + _EXACT_NAMES[exact_key]

    value = raw.replace("_", " ").replace("-", " ")
    value = re.sub(r"([a-zà-ÿ])([A-Z])", r"\1 \2", value)
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    value = re.sub(r"(?<=\d)(?=[A-Z])", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    for old, new in _COMPOUND_REPLACEMENTS:
        if old == "hospit":
            value = re.sub(r"hospit(?!alisation)", new, value)
        else:
            value = value.replace(old, new)
    value = re.sub(r"\s+", " ", value).strip()
    for old, new in _PHRASES:
        value = value.replace(old, new)

    words = [_WORDS.get(word, word) for word in value.split()]
    value = " ".join(words)
    value = re.sub(r"\bcreation\b", "création", value)
    value = re.sub(r"\bidentite\b", "identité", value)
    value = re.sub(r"\bmedecin\b", "médecin", value)
    value = re.sub(r"\bprealable\b", "préalable", value)
    value = re.sub(r"\s+", " ", value).strip()
    return prefix + value[:1].upper() + value[1:]
