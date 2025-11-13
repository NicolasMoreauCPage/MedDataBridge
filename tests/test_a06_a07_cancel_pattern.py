"""
Tests pour la validation du pattern A06/A07 CANCEL (annulation avec inversion).

Pattern: 
  - A06 CANCEL avec ZBE-6=A07 annule un A06 original (INSERT)
  - A07 CANCEL avec ZBE-6=A06 annule un A07 original (INSERT)
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.emit_on_create import generate_pam_hl7
from app.services.pam_validation import validate_hl7_structure, validate_pam_semantics


def test_a06_cancel_pattern():
    """Test que A06 CANCEL (avec ZBE-6=A07) génère le message correct."""
    
    # Créer un mouvement A06 CANCEL
    mouvement = Mouvement(
        mouvement_seq=2,
        venue_id=1,
        when=datetime.now(),
        trigger_event="A06",      # MÊME CODE que l'original
        action="CANCEL",          # Action = CANCEL
        original_trigger="A07",   # INVERSE: on annule A07
        nature="S",
        cancelled_movement_seq=1
    )
    
    # Générer le message HL7
    hl7_message = generate_pam_hl7(mouvement, operation="update")
    
    # Vérifier les segments clés
    assert "EVN|A06|" in hl7_message, "EVN doit contenir A06"
    assert "ZBE" in hl7_message, "ZBE segment requis"
    
    # Parser et vérifier ZBE
    segments = hl7_message.split('\r')
    zbe_segment = [s for s in segments if s.startswith('ZBE')][0]
    zbe_parts = zbe_segment.split('|')
    
    # ZBE|1|2||4|5|6|7|8|9
    # ZBE-4 = action, ZBE-6 = original_trigger
    assert zbe_parts[4] == "CANCEL", f"ZBE-4 doit être CANCEL, reçu: {zbe_parts[4]}"
    assert zbe_parts[6] == "A07", f"ZBE-6 doit être A07, reçu: {zbe_parts[6]}"
    assert zbe_parts[9] == "S", f"ZBE-9 (nature) doit être S, reçu: {zbe_parts[9]}"


def test_a07_cancel_pattern():
    """Test que A07 CANCEL (avec ZBE-6=A06) génère le message correct."""
    
    # Créer un mouvement A07 CANCEL
    mouvement = Mouvement(
        mouvement_seq=3,
        venue_id=1,
        when=datetime.now(),
        trigger_event="A07",      # MÊME CODE que l'original
        action="CANCEL",          # Action = CANCEL
        original_trigger="A06",   # INVERSE: on annule A06
        nature="H",
        cancelled_movement_seq=2
    )
    
    # Générer le message HL7
    hl7_message = generate_pam_hl7(mouvement, operation="update")
    
    # Vérifier les segments clés
    assert "EVN|A07|" in hl7_message, "EVN doit contenir A07"
    assert "ZBE" in hl7_message, "ZBE segment requis"
    
    # Parser et vérifier ZBE
    segments = hl7_message.split('\r')
    zbe_segment = [s for s in segments if s.startswith('ZBE')][0]
    zbe_parts = zbe_segment.split('|')
    
    # ZBE|1|2||4|5|6|7|8|9
    assert zbe_parts[4] == "CANCEL", f"ZBE-4 doit être CANCEL, reçu: {zbe_parts[4]}"
    assert zbe_parts[6] == "A06", f"ZBE-6 doit être A06, reçu: {zbe_parts[6]}"
    assert zbe_parts[9] == "H", f"ZBE-9 (nature) doit être H, reçu: {zbe_parts[9]}"


def test_a06_cancel_trigger_event_unchanged():
    """Test que trigger_event ne change pas en CANCEL (seulement action)."""
    
    # Mouvement A06 INSERT original
    mouvement_insert = Mouvement(
        mouvement_seq=1,
        venue_id=1,
        when=datetime.now(),
        trigger_event="A06",
        action="INSERT",
        nature="S"
    )
    
    # Mouvement A06 CANCEL (même trigger_event, action change)
    mouvement_cancel = Mouvement(
        mouvement_seq=2,
        venue_id=1,
        when=datetime.now() + timedelta(hours=1),
        trigger_event="A06",      # ← MÊME trigger_event
        action="CANCEL",          # ← action CHANGE
        original_trigger="A07",
        nature="S",
        cancelled_movement_seq=1
    )
    
    # Vérifier les propriétés
    assert mouvement_insert.trigger_event == mouvement_cancel.trigger_event, \
        "trigger_event doit rester le même"
    assert mouvement_insert.action != mouvement_cancel.action, \
        "action doit changer"
    assert mouvement_cancel.action == "CANCEL"
    assert mouvement_cancel.original_trigger == "A07"


def test_a06_cancel_inverse_logic():
    """Test que ZBE-6 (original_trigger) est l'inverse de trigger_event."""
    
    test_cases = [
        ("A06", "A07", "Annule A07 quand on envoie A06"),
        ("A07", "A06", "Annule A06 quand on envoie A07"),
    ]
    
    for trigger_event, expected_inverse, description in test_cases:
        mouvement = Mouvement(
            mouvement_seq=1,
            venue_id=1,
            when=datetime.now(),
            trigger_event=trigger_event,
            action="CANCEL",
            original_trigger=expected_inverse,
            nature="S" if trigger_event == "A06" else "H"
        )
        
        # Vérifier que l'inverse est respecté
        assert mouvement.original_trigger != mouvement.trigger_event, \
            f"{description}: original_trigger doit être différent"
        
        if mouvement.trigger_event == "A06":
            assert mouvement.original_trigger == "A07"
        elif mouvement.trigger_event == "A07":
            assert mouvement.original_trigger == "A06"


def test_a06_cancel_vs_a06_insert_nature():
    """Test que la nature est conservée entre INSERT et CANCEL."""
    
    # A06 INSERT: nature=S (passage vers externe)
    mouvement_insert = Mouvement(
        mouvement_seq=1,
        venue_id=1,
        when=datetime.now(),
        trigger_event="A06",
        action="INSERT",
        nature="S"
    )
    
    # A06 CANCEL: même nature
    mouvement_cancel = Mouvement(
        mouvement_seq=2,
        venue_id=1,
        when=datetime.now() + timedelta(hours=1),
        trigger_event="A06",
        action="CANCEL",
        original_trigger="A07",
        nature="S",  # ← MÊME
        cancelled_movement_seq=1
    )
    
    assert mouvement_insert.nature == mouvement_cancel.nature, \
        "Nature doit rester S dans les deux cas"


def test_cancelled_movement_seq_tracking():
    """Test que cancelled_movement_seq pointe correctement."""
    
    # Mouvement original
    original_seq = 5
    
    # Mouvement d'annulation
    mouvement_cancel = Mouvement(
        mouvement_seq=6,
        venue_id=1,
        when=datetime.now(),
        trigger_event="A06",
        action="CANCEL",
        original_trigger="A07",
        cancelled_movement_seq=original_seq,  # ← Pointe sur le original
        nature="S"
    )
    
    assert mouvement_cancel.cancelled_movement_seq == original_seq, \
        f"cancelled_movement_seq doit être {original_seq}"
    assert mouvement_cancel.mouvement_seq != mouvement_cancel.cancelled_movement_seq, \
        "Ne doit pas pointer sur soi-même"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
