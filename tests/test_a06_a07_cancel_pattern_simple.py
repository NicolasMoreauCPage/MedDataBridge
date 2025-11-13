"""
Tests pour la validation du pattern A06/A07 CANCEL (annulation avec inversion).

Pattern: 
  - A06 CANCEL avec ZBE-6=A07 annule un A06 original (INSERT)
  - A07 CANCEL avec ZBE-6=A06 annule un A07 original (INSERT)
"""

import pytest
from datetime import datetime, timedelta

from app.models import Mouvement


class TestA06A07CancelPattern:
    """Tests du pattern d'annulation A06/A07."""

    def test_a06_cancel_trigger_event_unchanged(self):
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


    def test_a06_cancel_inverse_logic(self):
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


    def test_a06_cancel_vs_a06_insert_nature(self):
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


    def test_a07_cancel_vs_a07_insert_nature(self):
        """Test que la nature est conservée entre INSERT et CANCEL pour A07."""
        
        # A07 INSERT: nature=H (passage depuis hospitalisation)
        mouvement_insert = Mouvement(
            mouvement_seq=1,
            venue_id=1,
            when=datetime.now(),
            trigger_event="A07",
            action="INSERT",
            nature="H"
        )
        
        # A07 CANCEL: même nature
        mouvement_cancel = Mouvement(
            mouvement_seq=2,
            venue_id=1,
            when=datetime.now() + timedelta(hours=1),
            trigger_event="A07",
            action="CANCEL",
            original_trigger="A06",
            nature="H",  # ← MÊME
            cancelled_movement_seq=1
        )
        
        assert mouvement_insert.nature == mouvement_cancel.nature, \
            "Nature doit rester H dans les deux cas"


    def test_cancelled_movement_seq_tracking(self):
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


    def test_a06_cancel_structure(self):
        """Test la structure complète d'un mouvement A06 CANCEL."""
        
        mouvement = Mouvement(
            mouvement_seq=3,
            venue_id=1,
            when=datetime.now(),
            trigger_event="A06",
            action="CANCEL",
            original_trigger="A07",
            nature="S",
            cancelled_movement_seq=2,
            uf_responsabilite="CARDIO",
            uf_soins_code="USCCU"
        )
        
        # Vérifier tous les champs
        assert mouvement.mouvement_seq == 3
        assert mouvement.venue_id == 1
        assert mouvement.trigger_event == "A06"
        assert mouvement.action == "CANCEL"
        assert mouvement.original_trigger == "A07"
        assert mouvement.nature == "S"
        assert mouvement.cancelled_movement_seq == 2
        assert mouvement.uf_responsabilite == "CARDIO"
        assert mouvement.uf_soins_code == "USCCU"


    def test_a07_cancel_structure(self):
        """Test la structure complète d'un mouvement A07 CANCEL."""
        
        mouvement = Mouvement(
            mouvement_seq=4,
            venue_id=1,
            when=datetime.now(),
            trigger_event="A07",
            action="CANCEL",
            original_trigger="A06",
            nature="H",
            cancelled_movement_seq=3
        )
        
        # Vérifier tous les champs
        assert mouvement.mouvement_seq == 4
        assert mouvement.trigger_event == "A07"
        assert mouvement.action == "CANCEL"
        assert mouvement.original_trigger == "A06"
        assert mouvement.nature == "H"
        assert mouvement.cancelled_movement_seq == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
