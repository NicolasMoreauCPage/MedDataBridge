# IHE PAM (Profile Application Management) — Validation guide

Ce document décrit des règles pratiques pour valider les messages IHE PAM et
les enchaînements (workflows) attendus par MedData_Bridge.

## 1. Objectif

- Fournir une check-list technique pour valider les messages PAM (segments, champs
  obligatoires, codages attendus).

- Proposer un outil de validation minimal `scripts/validate_pam.py` qui effectue
  des contrôles de conformité (message et workflow).

## 2. Règles de validation des messages

- Segments requis pour un message d'hospitalisation typique (ADT): `MSH`, `PID`, `PV1`.

- Codages HL7: vérifier que MSH-12 contient 2.5 ou 2.5.1 selon l'envoi attendu.

- Pour PAM, certains Z-segments (ZBE, ZBE-...) sont utilisés pour transmettre des
  métadonnées opérationnelles. Le validateur vérifiera la présence si configuré.

- Formats d'identifiants: XPN / CX / EI doivent respecter les longueurs attendues
  (ex. EI-1 <= 16 pour certains output MFN, mais PAM peut tolérer plus selon le profil).

### Exemples de contrôles rapides

- Vérifier la présence de `MSH` en première ligne et que `MSH-9` contient une valeur (ex.: `ADT^A01`).

- `PID-3` contient au moins un identifiant patient sous la forme `ID^^^SYSTEM&OID&ISO^PI`.

- `PV1-2` / `PV1-3` contiennent des codes de location valides.

## 3. Règles de validation des enchaînements (workflows)

L'objectif est de valider que les événements applicatifs arrivent dans un ordre
logique. Exemples de règles possibles:

- Admission (A01) doit précéder toute modification d'état liée au séjour (A08, A03 pour sortie en A03). 

- Sortie définitive (A03/A08 selon contexte) ne doit pas précéder l'admission.

- Suite d'événements pour un patient donné (PID-3) : A01 → A02/A08* → A03.

Le validateur `workflow` proposera des vérifications basiques :

- construction d'une timeline par `PID-3` à partir des fichiers fournis;

- détection d'anomalies temporelles (A03 avant A01, etc.);

- détection d'événements manquants (pas d'A01 avant un A03, etc.).

## 4. Usage de l'outil de validation

- Validation d'un seul message :

```bash
python3 scripts/validate_pam.py message path/to/message.hl7
```

- Validation d'un répertoire d'enchaînements pour workflow :

```bash
python3 scripts/validate_pam.py workflow path/to/messages_dir
```

## 5. Extensions possibles

  autorisées par service, code mappings, exceptions).


Annexe: Référence rapide des segments usuels utilisés en PAM

# Pour la documentation technique détaillée du pipeline d'intégration, voir :

# [Documentation technique IHE PAM (HTML)](IHE_PAM_TECHNIQUE.html)


