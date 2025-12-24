# Phase 4 - Error Pattern Analysis

**Generated**: 2025-12-05T15:09:53.405942

## Error Summary

| Status | Count | Percentage |
|--------|-------|------------|
| AA | 118 | 21.3% |
| AE | 362 | 65.3% |
| AR | 74 | 13.4% |

## Error Breakdown by Message Type

### UNKNOWN

- AA (Success): 118
- AE (Error): 362
- AR (Reject): 74


## Top Error Reasons

- **MSH|^~\&|STDCP2|20180114160959|MEDBRIDGEDATA|CPAGE|20251205140657||ACK|ACK20251205140657|2.5^FRA^2.5|MSA|AE|P|Unsupported message type: 6959604 (only ADT/MFN M05 supported)ERR|||207^Unsupported message type: 6959604 (only ADT/MFN M05 supported)^HL70357|E**: 35 occurrences
- **MSH|^~\&|GAPHL7|GAPHL7|CPAGE|CPAGE|20251205140657||ACK^A03|ACK20251205140657|P|2.5MSA|AE|852885|Segment ZBE obligatoire manquant pour le message ADT^A03. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A03. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 9 occurrences
- **MSH|^~\&|GAPHL7|GAPHL7|CPAGE|CPAGE|20251205140657||ACK^A01|ACK20251205140657|P|2.5MSA|AE|852862|Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 8 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^Z99|ACK20251205140657|P|2.5MSA|AR|1334220|Z99 message missing ZBE-1 (original movement identifier)ERR|||207^Z99 message missing ZBE-1 (original movement identifier)^HL70357|E**: 8 occurrences
- **MSH|^~\&|GAM|GAM|SILLAGE|SILLAGE|20251205140657||ACK^A01|ACK20251205140657|P|2.5^FRA^2.4MSA|AE|688|Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 7 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^A04|ACK20251205140657|P|2.5MSA|AE|1334147|Segment ZBE obligatoire manquant pour le message ADT^A04. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A04. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 7 occurrences
- **MSH|^~\&|CPAGE|CPAGE|SILLAGE|SILLAGE|20251205140657||ACK^A01|ACK20251205140657|P|2.5^FRA^2.4MSA|AE|520|Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A01. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 6 occurrences
- **MSH|^~\&|STDCP2|20180114161524|MEDBRIDGEDATA|CPAGE|20251205140657||ACK|ACK20251205140657|2.5^FRA^2.5|MSA|AE|P|Unsupported message type: 6959757 (only ADT/MFN M05 supported)ERR|||207^Unsupported message type: 6959757 (only ADT/MFN M05 supported)^HL70357|E**: 6 occurrences
- **MSH|^~\&|GAPHL7|GAPHL7|CPAGE|CPAGE|20251205140657||ACK^A02|ACK20251205140657|P|2.5MSA|AE|1336875|Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 6 occurrences
- **MSH|^~\&|STDCP2|20180114161524|MEDBRIDGEDATA|CPAGE|20251205140656||ACK|ACK20251205140656|2.5^FRA^2.5|MSA|AE|P|Unsupported message type: 6959757 (only ADT/MFN M05 supported)ERR|||207^Unsupported message type: 6959757 (only ADT/MFN M05 supported)^HL70357|E**: 6 occurrences
- **MSH|^~\&|OPHTIX|RECEPTION|EASILY|ENVOI|20251205140658||ACK^S12|ACK20251205140658|P|2.5MSA|AE|3341334|Unsupported message type: SIU (only ADT/MFN M05 supported)ERR|||207^Unsupported message type: SIU (only ADT/MFN M05 supported)^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHL7|GAPHL7|CPAGE|CPAGE|20251205140657||ACK^A05|ACK20251205140657|P|2.5MSA|AE|852212|Segment ZBE obligatoire manquant pour le message ADT^A05. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A05. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 5 occurrences
- **MSH|^~\&|STDCP2|20180114161004|MEDBRIDGEDATA|CPAGE|20251205140657||ACK|ACK20251205140657|2.5^FRA^2.5|MSA|AE|P|Unsupported message type: 6959622 (only ADT/MFN M05 supported)ERR|||207^Unsupported message type: 6959622 (only ADT/MFN M05 supported)^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^A05|ACK20251205140657|P|2.5MSA|AE|1334147|Segment ZBE obligatoire manquant pour le message ADT^A05. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A05. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^Z99|ACK20251205140657|P|2.5MSA|AR|1334306|Z99 message missing ZBE-1 (original movement identifier)ERR|||207^Z99 message missing ZBE-1 (original movement identifier)^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^A02|ACK20251205140657|P|2.5MSA|AE|1334306|Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHOS|GAPHOS|CPAGE|CPAGE|20251205140657||ACK^A06|ACK20251205140657|P|2.5MSA|AE|1334220|Segment ZBE obligatoire manquant pour le message ADT^A06. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A06. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 5 occurrences
- **MSH|^~\&|CPAGE|CPAGE|CRISTAL NET|CRISTAL NET|20251205140657||ACK^Z99|ACK20251205140657|P|2.5MSA|AR|1000009808|Z99 message missing ZBE-1 (original movement identifier)ERR|||207^Z99 message missing ZBE-1 (original movement identifier)^HL70357|E**: 5 occurrences
- **MSH|^~\&|GAPHL7|GAPHL7|CPAGE|CPAGE|20251205140656||ACK^A02|ACK20251205140656|P|2.5MSA|AE|1337155|Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A02. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 5 occurrences
- **MSH|^~\&|SILLAGE_MVT_IHE_E|SILLAGE_MVT_IHE_E|SILLAGE|SILLAGE|20251205140658||ACK^A04|ACK20251205140658|P|2.5^FRA^2.4MSA|AE|422|Segment ZBE obligatoire manquant pour le message ADT^A04. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.ERR|||207^Segment ZBE obligatoire manquant pour le message ADT^A04. Le profil IHE PAM France requiert le segment ZBE pour tous les messages de mouvement patient.^HL70357|E**: 4 occurrences
