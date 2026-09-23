"""Tables de correspondance des événements PAM."""






MOVEMENT_KIND_BY_TRIGGER = {
    # Événements Patient (pas de mouvement)
    "A28": "patient-add",       # Ajout patient (création)
    "A31": "patient-update",    # Mise à jour patient
    "A40": "patient-merge",     # Fusion de patients
    
    # Événements Admission
    "A04": "admission",         # Admission ambulatoire (consultation externe)
    "A05": "preadmission",      # Pré-admission
    "A06": "class-change",      # Changement classe ambulatoire → hospitalisation
    "A07": "class-change",      # Changement classe hospitalisation → ambulatoire
    
    # Événements Transfert/Sortie
    "A02": "transfer",          # Transfert
    "A03": "discharge",         # Sortie définitive
    "A21": "leave-out",         # Sortie temporaire (absence)
    "A22": "leave-return",      # Retour d'absence
    "A52": "leave-out-cancel",  # Annulation sortie temporaire
    "A53": "leave-return-cancel", # Annulation retour d'absence
    
    # Événements Annulation
    "A11": "admission-cancel",  # Annulation admission
    "A12": "transfer-cancel",   # Annulation transfert
    "A13": "discharge-cancel",  # Annulation sortie
    "A23": "registration-cancel", # Annulation enregistrement
    "A38": "preadmission-cancel", # Annulation pré-admission
    
    # Autres
    "A29": "patient-delete",    # Suppression patient
    "A54": "doctor-change",     # Changement médecin
    "A55": "doctor-change-cancel", # Annulation changement médecin
}

MOVEMENT_STATUS_BY_TRIGGER = {
    "A05": "planned",
    "A11": "cancelled",
    "A23": "cancelled",
    "A38": "cancelled",
    "A12": "cancelled",
    "A13": "cancelled",
    "A21": "leave",
    "A52": "leave",
    "A22": "completed",
    "A53": "completed",
    "A54": "completed",
    "A55": "cancelled",
}

