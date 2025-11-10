"""
Tests pour la génération de messages MFN^M05 pour les organisations (EntiteJuridique)

Objectifs:
- Valider la conformité des messages MFN pour organisations
- Vérifier l'usage correct des segments STF/PRA
- Tester la génération pour EntiteJuridique
- Valider le format MSH aligné sur CPAGE
"""
import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, select
from app.models_structure_fhir import EntiteJuridique, GHTContext
from app.services.mfn_organization import generate_mfn_organization_message


@pytest.fixture
def memory_session():
    """Session en mémoire pour tests isolés avec un GHT par défaut"""
    engine = create_engine("sqlite:///:memory:")
    from app.models_structure_fhir import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Créer un GHT par défaut pour tous les tests
        ght = GHTContext(name="GHT Test", short_name="GHT-TEST")
        session.add(ght)
        session.commit()
        session.refresh(ght)
        # Stocker l'ID du GHT dans la session pour utilisation dans les tests
        session.info["default_ght_id"] = ght.id
        yield session


def parse_msh_fields(msh_line: str) -> dict:
    """Parse les champs du segment MSH"""
    fields = msh_line.split("|")
    return {
        "sending_app": fields[2],
        "sending_facility": fields[3],
        "receiving_app": fields[4],
        "receiving_facility": fields[5],
        "timestamp": fields[6],
        "message_type": fields[8],
        "message_control_id": fields[9],
        "processing_id": fields[10],
        "version": fields[11],
        "country_code": fields[16] if len(fields) > 16 else None,
        "character_set": fields[17] if len(fields) > 17 else None,
    }


def parse_mfi_fields(mfi_line: str) -> dict:
    """Parse les champs du segment MFI"""
    fields = mfi_line.split("|")
    return {
        "master_file_id": fields[1],
        "master_file_app_id": fields[2],
        "file_level_event_code": fields[3],
        "response_level_code": fields[6] if len(fields) > 6 else None,
    }


def parse_mfe_fields(mfe_line: str) -> dict:
    """Parse les champs du segment MFE"""
    fields = mfe_line.split("|")
    return {
        "record_level_event_code": fields[1],
        "primary_key_value": fields[4],
        "primary_key_value_type": fields[5] if len(fields) > 5 else None,
    }


def parse_stf_fields(stf_line: str) -> dict:
    """Parse les champs du segment STF (Staff Identification)"""
    fields = stf_line.split("|")
    return {
        "primary_key_value": fields[1],
        "staff_identifier_list": fields[2],
        "staff_name": fields[3],
    }


def parse_pra_fields(pra_line: str) -> dict:
    """Parse les champs du segment PRA (Practitioner Detail)"""
    fields = pra_line.split("|")
    return {
        "primary_key_value": fields[1],
        "practitioner_category": fields[3] if len(fields) > 3 else None,
    }


class TestMFNOrganizationMSH:
    """Tests du segment MSH pour MFN^M05 Organization"""
    
    def test_mfn_org_msh_structure_format(self, memory_session):
        """Valide le format MSH conforme CPAGE"""
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.replace("\r", "").split("\n")
        msh = parse_msh_fields(lines[0])
        
        # Validations MSH
        assert msh["message_type"] == "MFN^M05^MFN_M05", "Type de message incorrect"
        assert msh["processing_id"] == "P", "Processing ID doit être P (Production)"
        assert msh["version"] == "2.5^FRA^2.11", "Version doit être 2.5^FRA^2.11 (IHE PAM France 2.11)"
        assert msh["country_code"] == "FRA", "MSH-17 (Country Code) doit être FRA"
        assert msh["character_set"] == "8859/1", "MSH-18 (Character Set) doit être 8859/1 (ISO-8859-1)"
    
    def test_mfn_org_msh_field_count(self, memory_session):
        """Valide le nombre de champs MSH (pas de pipes vides inutiles)"""
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.split("\n")
        msh_line = lines[0]
        
        parts = msh_line.split("|")
        assert len(parts) >= 18, "MSH doit avoir au moins 18 champs"
        
        # Vérifier les champs vides (13 à 16)
        assert parts[12] == "", "MSH-13 (Sequence Number) doit être vide"
        assert parts[13] == "", "MSH-14 (Continuation Pointer) doit être vide"
        assert parts[14] == "", "MSH-15 (Accept Acknowledgment Type) doit être vide"
        assert parts[15] == "", "MSH-16 (Application Acknowledgment Type) doit être vide"


class TestMFNOrganizationMFI:
    """Tests du segment MFI (Master File Identification)"""
    
    def test_mfi_organization(self, memory_session):
        """Valide le segment MFI pour les organisations"""
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.split("\n")
        mfi = parse_mfi_fields(lines[1])
        
        assert mfi["master_file_id"] == "ORG", "MFI-1 doit être ORG (organization master file)"
        assert mfi["master_file_app_id"] == "MEDBRIDGE_ORG", "MFI-2 doit identifier l'application"
        assert mfi["file_level_event_code"] == "REP", "MFI-3 doit être REP (replace/snapshot)"
        assert mfi["response_level_code"] == "AL", "MFI-6 doit être AL (always)"


class TestMFNOrganizationEntiteJuridique:
    """Tests MFN pour EntiteJuridique"""
    
    def test_generate_mfn_entite_juridique(self, memory_session):
        """Génère un MFN pour une EntiteJuridique"""
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.split("\n")
        
        # Trouver les segments pour cette EJ
        mfe_idx = next(i for i, l in enumerate(lines) if l.startswith("MFE|"))
        stf_idx = mfe_idx + 1
        pra_idx = stf_idx + 1
        
        mfe = parse_mfe_fields(lines[mfe_idx])
        stf = parse_stf_fields(lines[stf_idx])
        pra = parse_pra_fields(lines[pra_idx])
        
        # Validations MFE
        assert mfe["record_level_event_code"] == "MAD", "MFE-1 doit être MAD (Master File Add)"
        assert "010000123" in mfe["primary_key_value"], "MFE-4 doit contenir le FINESS"
        assert mfe["primary_key_value_type"] == "ORG", "MFE-5 doit être ORG (Organization)"
        
        # Validations STF
        assert "CHU Test" in stf["staff_name"], "STF-3 doit contenir le nom de l'organisation"
        
        # Validations PRA
        assert pra["practitioner_category"] == "ORG", "PRA-3 doit être ORG (Organization)"
    
    def test_mfn_ej_identifier_format(self, memory_session):
        """Valide le format de l'identifiant CX avec FINESS"""
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.split("\n")
        
        mfe_line = next(l for l in lines if l.startswith("MFE|"))
        mfe = parse_mfe_fields(mfe_line)
        
        # Format attendu: FINESS^^^FINESS&OID&ISO^FINEJ
        identifier = mfe["primary_key_value"]
        assert "010000123" in identifier, "Identifiant doit contenir le FINESS"
        assert "FINESS" in identifier, "Identifiant doit contenir le système FINESS"
        assert "1.2.250.1.71.4.2.2" in identifier, "Identifiant doit contenir l'OID FINESS"
        assert "ISO" in identifier, "Identifiant doit contenir ISO"
        assert "FINEJ" in identifier, "Identifiant doit contenir le type FINEJ"


class TestMFNOrganizationMultiple:
    """Tests MFN avec plusieurs EntiteJuridique"""
    
    def test_generate_mfn_multiple_ej(self, memory_session):
        """Génère un MFN pour plusieurs EntiteJuridique"""
        ej1 = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test 1",
            short_name="CHU1",
            ght_context_id=memory_session.info['default_ght_id']
        )
        ej2 = EntiteJuridique(
            finess_ej="020000456",
            name="CHU Test 2",
            short_name="CHU2",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej1)
        memory_session.add(ej2)
        memory_session.commit()
        
        # Générer le MFN snapshot (sans spécifier ej)
        message = generate_mfn_organization_message(memory_session)
        lines = message.split("\n")
        
        # Compter les MFE
        mfe_count = sum(1 for l in lines if l.startswith("MFE|"))
        assert mfe_count == 2, "Doit contenir 2 segments MFE (un par EJ)"
        
        # Vérifier la présence des deux FINESS
        message_text = "\n".join(lines)
        assert "010000123" in message_text, "Doit contenir le FINESS de EJ1"
        assert "020000456" in message_text, "Doit contenir le FINESS de EJ2"
    
    def test_generate_mfn_single_ej_filter(self, memory_session):
        """Génère un MFN pour une seule EntiteJuridique spécifique"""
        ej1 = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test 1",
            short_name="CHU1",
            ght_context_id=memory_session.info['default_ght_id']
        )
        ej2 = EntiteJuridique(
            finess_ej="020000456",
            name="CHU Test 2",
            short_name="CHU2",
            ght_context_id=memory_session.info['default_ght_id']
        )
        memory_session.add(ej1)
        memory_session.add(ej2)
        memory_session.commit()
        
        # Générer le MFN pour EJ1 seulement
        message = generate_mfn_organization_message(memory_session, ej=ej1)
        lines = message.split("\n")
        
        # Compter les MFE
        mfe_count = sum(1 for l in lines if l.startswith("MFE|"))
        assert mfe_count == 1, "Doit contenir 1 segment MFE seulement"
        
        # Vérifier la présence de EJ1 et absence de EJ2
        message_text = "\n".join(lines)
        assert "010000123" in message_text, "Doit contenir le FINESS de EJ1"
        assert "020000456" not in message_text, "Ne doit PAS contenir le FINESS de EJ2"


class TestMFNOrganizationGHT:
    """Tests MFN avec contexte GHT"""
    
    def test_mfn_ej_with_ght(self, memory_session):
        """Génère un MFN pour une EJ avec lien GHT"""
        ght = GHTContext(
            name="GHT Île-de-France",
            short_name="GHT-IDF"
        )
        memory_session.add(ght)
        memory_session.commit()
        memory_session.refresh(ght)
        
        ej = EntiteJuridique(
            finess_ej="010000123",
            name="CHU Test",
            short_name="CHU",
            ght_context_id=ght.id
        )
        memory_session.add(ej)
        memory_session.commit()
        
        message = generate_mfn_organization_message(memory_session, ej=ej)
        lines = message.split("\n")
        
        # Vérifier la présence du segment AFF (Affiliation)
        aff_lines = [l for l in lines if l.startswith("AFF|")]
        assert len(aff_lines) > 0, "Doit contenir un segment AFF pour le lien GHT"
        
        # Vérifier que le nom du GHT apparaît
        message_text = "\n".join(lines)
        assert "GHT" in message_text or "GHT-IDF" in message_text, "Doit contenir une référence au GHT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
