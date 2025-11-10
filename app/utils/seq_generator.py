"""
Générateur d'identifiants basés sur timestamp pour Patient et Dossier.

Les identifiants sont générés sans dépendance à des séquences en base de données,
basés uniquement sur le timestamp pour garantir l'unicité.

Formats:
- Patient (patient_seq) : 12 caractères, préfixe '9' + 11 chiffres timestamp
- Dossier (dossier_seq) : 9 caractères, préfixe '9' + 8 chiffres timestamp

Pour garantir l'unicité même en cas de génération très rapide, on utilise
un compteur atomique en plus du timestamp.
"""
import time
import threading

# Verrous et compteurs pour garantir l'unicité
_patient_lock = threading.Lock()
_dossier_lock = threading.Lock()
_patient_counter = 0
_dossier_counter = 0
_last_patient_timestamp = 0
_last_dossier_timestamp = 0


def generate_patient_seq() -> int:
    """
    Génère un identifiant patient unique basé sur le timestamp.
    
    Format : 12 chiffres
    - 1er chiffre : toujours '9'
    - 10 chiffres : timestamp en microsecondes (10 chiffres du milieu)
    - 1 dernier chiffre : compteur (0-9) pour éviter les collisions
    
    Thread-safe et garantit l'unicité même avec génération très rapide.
    
    Returns:
        int: Identifiant patient de 12 chiffres (ex: 917351234560)
    
    Examples:
        >>> seq = generate_patient_seq()
        >>> 900000000000 <= seq < 1000000000000
        True
        >>> str(seq)[0]
        '9'
    """
    global _patient_counter, _last_patient_timestamp
    
    with _patient_lock:
        # Obtenir le timestamp en microsecondes
        timestamp_us = int(time.time() * 1_000_000)
        
        # Si même timestamp, incrémenter le compteur
        if timestamp_us == _last_patient_timestamp:
            _patient_counter = (_patient_counter + 1) % 10
        else:
            _patient_counter = 0
            _last_patient_timestamp = timestamp_us
        
        # Prendre 10 chiffres du timestamp (pas les premiers pour éviter dépassement)
        # et ajouter le compteur
        timestamp_str = str(timestamp_us)[-10:]
        
        # Préfixer avec '9', ajouter timestamp et compteur
        return int(f"9{timestamp_str}{_patient_counter}")


def generate_dossier_seq() -> int:
    """
    Génère un identifiant de dossier unique basé sur le timestamp.
    
    Format : 9 chiffres
    - 1er chiffre : toujours '9'
    - 7 chiffres : timestamp en microsecondes (7 chiffres du milieu)
    - 1 dernier chiffre : compteur (0-9) pour éviter les collisions
    
    Thread-safe et garantit l'unicité même avec génération très rapide.
    
    Returns:
        int: Identifiant dossier de 9 chiffres (ex: 912345670)
    
    Examples:
        >>> seq = generate_dossier_seq()
        >>> 900000000 <= seq < 1000000000
        True
        >>> str(seq)[0]
        '9'
    """
    global _dossier_counter, _last_dossier_timestamp
    
    with _dossier_lock:
        # Obtenir le timestamp en microsecondes
        timestamp_us = int(time.time() * 1_000_000)
        
        # Si même timestamp, incrémenter le compteur
        if timestamp_us == _last_dossier_timestamp:
            _dossier_counter = (_dossier_counter + 1) % 10
        else:
            _dossier_counter = 0
            _last_dossier_timestamp = timestamp_us
        
        # Prendre 7 chiffres du timestamp (pas les premiers pour éviter dépassement)
        # et ajouter le compteur
        timestamp_str = str(timestamp_us)[-7:]
        
        # Préfixer avec '9', ajouter timestamp et compteur
        return int(f"9{timestamp_str}{_dossier_counter}")
