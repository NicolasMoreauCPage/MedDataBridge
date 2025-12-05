#!/usr/bin/env python3
"""
Renomme intelligemment les scénarios en utilisant:
1. Les triggers HL7 (ADT, SIU)
2. Le nom descriptif amélioré
3. Le nombre de messages
"""

import re
from sqlmodel import Session, select
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep

# Mapping des triggers vers descriptions
TRIGGER_DESCRIPTIONS = {
    "A01": "Admission",
    "A02": "Transfer",
    "A03": "Discharge",
    "A04": "Register",
    "A05": "Pre-Admission",
    "A06": "Change Attr.",
    "A11": "Cancel Admit",
    "A12": "Cancel Transfer",
    "A13": "Cancel Discharge",
    "A21": "Bed Status",
    "A22": "Pending Admission",
    "A28": "Add Person",
    "A31": "Update Person",
    "A38": "Cancelled Pre-Admission",
    "A40": "Merge Patient",
    "A44": "Move Patient",
    "A47": "Change Alternate ID",
    "A54": "Update Account",
    "S12": "Appt Booking",
    "S13": "Appt Rescheduling",
    "S14": "Appt Cancellation",
    "S15": "Appt Interruption",
    "Z80": "Bed Config.",
    "Z99": "Custom",
}

# Mots-clés à normaliser (en ordre de priorité)
NORMALIZE_PATTERNS = [
    (r'creationipp', "Create IPP"),
    (r'maternite|maternity', "Maternity"),
    (r'neonatal', "Neonatal"),
    (r'medecin\s*traitant', "GP"),
    (r'fusion\s*avec', "merged with"),
    (r'preadmission|pread', "Pre-Admission"),
    (r'hospit(alisation)?', "Hospitalization"),
    (r'jour', "Same-Day"),
    (r'urgence(s)?', "Emergency"),
    (r'eh(pad)?', "EHPAD"),
    (r'externe', "External"),
    (r'statut', "Status"),
    (r'changement', "Change"),
    (r'suivi\s?par', "followed by"),
    (r'inutile', "unnecessary"),
    (r'emplacement|location', "Location"),
    (r'responsable|resp', "Responsible"),
    (r'insertion', "Insert"),
    (r'update', "Update"),
    (r'complexe|complex', "Complex"),
    (r'simple', "Simple"),
    (r'sorties?|sortie', "Discharge"),
    (r'deces|death', "Death"),
    (r'transfert', "Transfer"),
    (r'retour', "Return"),
    (r'psy|psychiatr', "Psychiatry"),
    (r'cora', "Cora"),
    (r'sillage', "Sillage"),
    (r'cristal|crystal', "Crystal"),
    (r'cloture', "Closure"),
    (r'administrative|admin', "Admin"),
    (r'siu', "SIU"),
    (r'rdv', "Appointment"),
    (r'fusion', "Merge"),
    (r'rattachement', "Attachment"),
    (r'seance(s)?', "Session"),
    (r'suppression', "Suppression"),
    (r'intermediaire', "Intermediate"),
    (r'autos', "Auto"),
    (r'prp', "PRP"),
    (r'fugue', "Escape"),
    (r'permission', "Permission"),
    (r'annul', "Cancel"),
    (r'venue', "Venue"),
    (r'mouvement|mvt', "Movement"),
    (r'internonautorise|non\s*autorise', "Unauthorized"),
    (r'iteratif', "Iterative"),
    (r'meme', "Same"),
    (r'entree', "Entry"),
    (r'contrainte', "Constrain"),
    (r'police', "Police"),
    (r'mutation', "Mutation"),
    (r'uf', "UF"),
    (r'bb', "BB"),
    (r'lit', "Bed"),
    (r'dossier', "Dossier"),
]

def extract_triggers(scenario):
    """Extrait les triggers des messages HL7"""
    triggers = []
    if scenario.steps:
        for step in scenario.steps:
            if step.payload and 'MSH' in step.payload:
                parts = step.payload.split('\r')
                for part in parts[:5]:
                    if part.startswith('MSH'):
                        msh_parts = part.split('|')
                        if len(msh_parts) > 8:
                            trigger = msh_parts[8]  # ADT^A01
                            if '^' in trigger:
                                code = trigger.split('^')[1]
                                if code:
                                    triggers.append(code)
                        break
    return sorted(list(set(triggers)))

def normalize_name(name):
    """Normalise un nom"""
    name = name.lower().strip()
    # Retirer le préfixe IHE PAM
    if name.startswith('ihe pam - '):
        name = name[10:]
    
    # Appliquer les normalisations dans l'ordre de priorité
    for pattern, replacement in NORMALIZE_PATTERNS:
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    
    # Nettoyer
    name = re.sub(r'\s+', ' ', name).strip()
    # Supprimer les caractères spéciaux sauf espaces et tirets
    name = re.sub(r'[^a-z0-9\s&-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def generate_intelligent_name(scenario):
    """Génère un nom intelligent pour le scénario"""
    triggers = extract_triggers(scenario)
    msg_count = len(scenario.steps) if scenario.steps else 0
    
    # Extraire nom descriptif
    original_name = scenario.name.replace("IHE PAM - ", "").strip()
    
    # Construire le nouveau nom
    parts = []
    
    # Ajouter les triggers (max 3, sinon résumer)
    if triggers:
        trigger_descs = [TRIGGER_DESCRIPTIONS.get(t, t) for t in triggers]
        if len(trigger_descs) <= 3:
            parts.append(" + ".join(trigger_descs))
        else:
            # Trop de triggers, utiliser seulement les principaux
            main_triggers = " + ".join(trigger_descs[:2])
            parts.append(f"{main_triggers} + ... ({len(triggers)} events)")
    
    # Ajouter le nombre de messages
    if msg_count > 0:
        parts.append(f"({msg_count} msg)")
    
    new_name = " ".join(parts)
    
    # Formatage final
    new_name = f"IHE PAM - {new_name}"
    
    return new_name

def main():
    """Renomme tous les scénarios"""
    with Session(engine) as session:
        scenarios = session.exec(select(InteropScenario)).all()
        
        print(f"📋 Renaming {len(scenarios)} scenarios...\n")
        
        changes = []
        for i, scenario in enumerate(scenarios, 1):
            new_name = generate_intelligent_name(scenario)
            
            if new_name != scenario.name:
                changes.append((scenario.name, new_name))
                if i <= 20 or i % 10 == 0:
                    print(f"{i:3}. {scenario.name}")
                    print(f"    → {new_name}\n")
                scenario.name = new_name
        
        # Persister
        session.add_all(scenarios)
        session.commit()
        
        print(f"\n✅ {len(changes)} scenarios renamed")
        print(f"✅ {len(scenarios) - len(changes)} scenarios unchanged")

if __name__ == "__main__":
    main()
