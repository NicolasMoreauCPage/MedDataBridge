"""
Tests pour la génération de messages MFN^M05 pour les structures (locations)

Objectifs:
- Valider la conformité des messages MFN générés
- Vérifier l'usage correct des vocabulaires dans les segments LCH/LRL
- Tester la génération pour tous les types d'entités (EG, Pole, Service, UF, UH, Chambre, Lit)
- Valider le format MSH aligné sur CPAGE (2.5^FRA^2.11, FRA, 8859/1)
"""
import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, select
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit
)
from app.services.mfn_structure import generate_mfn_message


@pytest.fixture
def memory_session():
    """Session en mémoire pour tests isolés"""
    engine = create_engine("sqlite:///:memory:")
    from app.models_structure import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
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


def parse_loc_fields(loc_line: str) -> dict:
    """Parse les champs du segment LOC"""
    fields = loc_line.split("|")
    return {
        "primary_key_value": fields[1],
        "location_type": fields[3],
        "location_description": fields[4] if len(fields) > 4 else None,
    }


def parse_lch_fields(lch_line: str) -> dict:
    """Parse les champs du segment LCH (Location Characteristic)"""
    fields = lch_line.split("|")
    char_code = fields[4] if len(fields) > 4 else ""
    char_value = fields[5] if len(fields) > 5 else ""
    
    # Format: CODE^Description^CodingSystem
    code_parts = char_code.split("^")
    return {
        "primary_key_value": fields[1],
        "characteristic_code": code_parts[0] if code_parts else "",
        "characteristic_description": code_parts[1] if len(code_parts) > 1 else "",
        "coding_system": code_parts[2] if len(code_parts) > 2 else "",
        "characteristic_value": char_value.lstrip("^") if char_value else "",
    }


def parse_lrl_fields(lrl_line: str) -> dict:
    """Parse les champs du segment LRL (Location Relationship)"""
    fields = lrl_line.split("|")
    # Format LRL: LRL|PL1|SegmentAction|OrganizationUnitType|RelType||RelIdValue
    # fields[3] = OrganizationUnitType (vide)
    # fields[4] = RelType (CODE^Description^CodingSystem)
    # fields[6] = RelIdValue
    rel_code = fields[4] if len(fields) > 4 else ""
    rel_value = fields[6] if len(fields) > 6 else ""
    
    code_parts = rel_code.split("^")
    return {
        "primary_key_value": fields[1],
        "relationship_code": code_parts[0] if code_parts else "",
        "relationship_description": code_parts[1] if len(code_parts) > 1 else "",
        "coding_system": code_parts[2] if len(code_parts) > 2 else "",
        "related_location_value": rel_value,
    }


class TestMFNStructureMSH:
    """Tests du segment MSH pour MFN^M05"""
    
    def test_mfn_msh_structure_format(self, memory_session):
        """Valide le format MSH conforme CPAGE"""
        # Créer une EG minimale
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU",
            physical_type="si"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        # Générer le message MFN
        message = generate_mfn_message(memory_session)
        lines = message.split("\n")
        msh = parse_msh_fields(lines[0])
        
        # Validations MSH
        assert msh["message_type"] == "MFN^M05^MFN_M05", "Type de message incorrect"
        assert msh["processing_id"] == "P", "Processing ID doit être P (Production)"
        assert msh["version"] == "2.5^FRA^2.11", "Version doit être 2.5^FRA^2.11 (IHE PAM France 2.11)"
        assert msh["country_code"] == "FRA", "MSH-17 (Country Code) doit être FRA"
        assert msh["character_set"] == "8859/1", "MSH-18 (Character Set) doit être 8859/1 (ISO-8859-1)"
    
    def test_mfn_msh_field_count(self, memory_session):
        """Valide le nombre de champs MSH (pas de pipes vides inutiles)"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session)
        lines = message.split("\n")
        msh_line = lines[0]
        
        # Compter les pipes entre version (MSH-12) et country code (MSH-17)
        # Format attendu: ...P|2.5^FRA^2.11|||||FRA|8859/1
        # MSH-13 à MSH-16 = 4 champs vides = 5 pipes
        parts = msh_line.split("|")
        assert len(parts) >= 18, "MSH doit avoir au moins 18 champs"
        
        # Vérifier les champs vides (13 à 16)
        assert parts[12] == "", "MSH-13 (Sequence Number) doit être vide"
        assert parts[13] == "", "MSH-14 (Continuation Pointer) doit être vide"
        assert parts[14] == "", "MSH-15 (Accept Acknowledgment Type) doit être vide"
        assert parts[15] == "", "MSH-16 (Application Acknowledgment Type) doit être vide"


class TestMFNStructureMFI:
    """Tests du segment MFI (Master File Identification)"""
    
    def test_mfi_structure(self, memory_session):
        """Valide le segment MFI pour les structures"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session)
        lines = message.split("\n")
        mfi = parse_mfi_fields(lines[1])
        
        assert mfi["master_file_id"] == "LOC", "MFI-1 doit être LOC (location master file)"
        assert mfi["master_file_app_id"] == "CPAGE_LOC_FRA", "MFI-2 doit identifier l'application"
        assert mfi["file_level_event_code"] == "REP", "MFI-3 doit être REP (replace/snapshot)"
        assert mfi["response_level_code"] == "AL", "MFI-6 doit être AL (always)"


class TestMFNStructureEntiteGeographique:
    """Tests MFN pour EntiteGeographique"""
    
    def test_generate_mfn_entite_geographique(self, memory_session):
        """Génère un MFN pour une EntiteGeographique"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU",
            finess="010000123",
            address_line1="1 rue de l'Hôpital",
            address_postalcode="75001",
            address_city="Paris"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session, eg_identifier="EG001")
        lines = message.split("\n")
        
        # Trouver les segments pour cette EG
        mfe_idx = next(i for i, l in enumerate(lines) if l.startswith("MFE|") and "EG001" in l)
        loc_idx = mfe_idx + 1
        
        mfe = parse_mfe_fields(lines[mfe_idx])
        loc = parse_loc_fields(lines[loc_idx])
        
        # Validations MFE
        assert mfe["record_level_event_code"] == "MAD", "MFE-1 doit être MAD (Master File Add)"
        assert "EG001" in mfe["primary_key_value"], "MFE-4 doit contenir l'identifiant EG001"
        assert mfe["primary_key_value_type"] == "PL", "MFE-5 doit être PL (Person Location)"
        
        # Validations LOC
        assert "EG001" in loc["primary_key_value"], "LOC-1 doit contenir l'identifiant"
        assert loc["location_type"] == "M", "LOC-3 doit être M (établissement juridique)"
    
    def test_mfn_eg_lch_vocabulary(self, memory_session):
        """Valide l'usage des vocabulaires dans les segments LCH pour EG"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU",
            finess="010000123",
            address_line1="1 rue de l'Hôpital",
            address_postalcode="75001",
            address_city="Paris"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session, eg_identifier="EG001")
        lines = message.split("\n")
        
        # Extraire tous les segments LCH pour cette EG
        lch_lines = [l for l in lines if l.startswith("LCH|") and "EG001" in l]
        assert len(lch_lines) > 0, "Doit contenir des segments LCH"
        
        # Parser les LCH
        lch_segments = [parse_lch_fields(l) for l in lch_lines]
        
        # Vérifier les codes de vocabulaire attendus
        characteristic_codes = {lch["characteristic_code"] for lch in lch_segments}
        
        # Codes obligatoires
        assert "ID_GLBL" in characteristic_codes, "Doit contenir ID_GLBL (Identifiant unique global)"
        assert "LBL" in characteristic_codes, "Doit contenir LBL (Libellé)"
        assert "LBL_CRT" in characteristic_codes, "Doit contenir LBL_CRT (Libellé court)"
        
        # Codes facultatifs présents
        assert "ADRS_1" in characteristic_codes, "Doit contenir ADRS_1 (Adresse 1)"
        assert "CD_PSTL" in characteristic_codes, "Doit contenir CD_PSTL (Code postal)"
        assert "VL" in characteristic_codes, "Doit contenir VL (Ville)"
        assert "FNS" in characteristic_codes, "Doit contenir FNS (Code FINESS)"
        
        # Vérifier le coding system
        for lch in lch_segments:
            assert lch["coding_system"] == "L", f"Tous les codes doivent être locaux (^L), trouvé: {lch['coding_system']}"


class TestMFNStructureService:
    """Tests MFN pour Service"""
    
    def test_generate_mfn_service_with_pole(self, memory_session):
        """Génère un MFN pour Service avec son Pôle"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU",
            physical_type="si"
        )
        memory_session.add(eg)
        memory_session.commit()
        memory_session.refresh(eg)
        
        pole = Pole(
            identifier="POLE001",
            name="Pôle Médecine",
            short_name="P-MED",
            physical_type="wa",
            entite_geo_id=eg.id
        )
        memory_session.add(pole)
        memory_session.commit()
        memory_session.refresh(pole)
        
        service = Service(
            identifier="SRV001",
            name="Service Cardiologie",
            short_name="CARDIO",
            physical_type="wa",
            service_type="mco",
            pole_id=pole.id
        )
        memory_session.add(service)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session, eg_identifier="EG001")
        lines = message.split("\n")
        
        # Trouver le service
        srv_mfe_idx = next(i for i, l in enumerate(lines) if l.startswith("MFE|") and "SRV001" in l)
        srv_loc = parse_loc_fields(lines[srv_mfe_idx + 1])
        
        assert srv_loc["location_type"] == "D", "LOC-3 doit être D (Service)"
        
        # Vérifier la relation LRL avec le pôle
        lrl_lines = [l for l in lines if l.startswith("LRL|") and "SRV001" in l]
        assert len(lrl_lines) > 0, "Service doit avoir une relation LRL avec le pôle"
        
        lrl = parse_lrl_fields(lrl_lines[0])
        assert lrl["relationship_code"] == "LCLSTN", "Relation doit être LCLSTN (localisation)"
        assert "POLE001" in lrl["related_location_value"], "Relation doit pointer vers POLE001"


class TestMFNStructureCompleteHierarchy:
    """Tests MFN avec hiérarchie complète"""
    
    def test_generate_mfn_complete_hierarchy(self, memory_session):
        """Génère un MFN avec hiérarchie complète EG > Pole > Service > UF > UH > Chambre > Lit"""
        # Créer la hiérarchie
        eg = EntiteGeographique(identifier="EG001", name="CHU Test", short_name="CHU", physical_type="si")
        memory_session.add(eg)
        memory_session.commit()
        memory_session.refresh(eg)
        
        pole = Pole(identifier="POLE001", name="Pôle Med", short_name="P-MED", physical_type="wa", entite_geo_id=eg.id)
        memory_session.add(pole)
        memory_session.commit()
        memory_session.refresh(pole)
        
        service = Service(identifier="SRV001", name="Cardio", short_name="CARDIO", physical_type="wa", service_type="mco", pole_id=pole.id)
        memory_session.add(service)
        memory_session.commit()
        memory_session.refresh(service)
        
        uf = UniteFonctionnelle(identifier="UF001", name="UF Cardio", short_name="UF-CARDIO", physical_type="wa", service_id=service.id)
        memory_session.add(uf)
        memory_session.commit()
        memory_session.refresh(uf)
        
        uh = UniteHebergement(identifier="UH001", name="UH Cardio", short_name="UH-CARDIO", physical_type="wa", unite_fonctionnelle_id=uf.id)
        memory_session.add(uh)
        memory_session.commit()
        memory_session.refresh(uh)
        
        chambre = Chambre(identifier="CH001", name="Chambre 101", short_name="CH101", physical_type="ro", unite_hebergement_id=uh.id)
        memory_session.add(chambre)
        memory_session.commit()
        memory_session.refresh(chambre)
        
        lit = Lit(identifier="LIT001", name="Lit 101A", short_name="L101A", physical_type="bd", chambre_id=chambre.id)
        memory_session.add(lit)
        memory_session.commit()
        
        # Générer le MFN
        message = generate_mfn_message(memory_session, eg_identifier="EG001")
        lines = message.split("\n")
        
        # Vérifier la présence de tous les types
        types_found = set()
        for line in lines:
            if line.startswith("LOC|"):
                loc = parse_loc_fields(line)
                types_found.add(loc["location_type"])
        
        assert "M" in types_found, "Doit contenir une Entité Géographique (M)"
        assert "P" in types_found, "Doit contenir un Pôle (P)"
        assert "D" in types_found, "Doit contenir un Service (D)"
        assert "UF" in types_found, "Doit contenir une UF"
        assert "UH" in types_found, "Doit contenir une UH"
        assert "CH" in types_found, "Doit contenir une Chambre"
        assert "LIT" in types_found, "Doit contenir un Lit"
        
        # Vérifier les relations
        lrl_lines = [l for l in lines if l.startswith("LRL|")]
        assert len(lrl_lines) >= 6, "Doit contenir au moins 6 relations (Service->Pole, UF->Service, UH->UF, Chambre->UH, Lit->Chambre, Pole->EG)"


class TestMFNStructureVocabulary:
    """Tests de validation des vocabulaires MFN"""
    
    def test_lch_coding_system_local(self, memory_session):
        """Tous les codes LCH doivent utiliser le système local (^L)"""
        eg = EntiteGeographique(
            identifier="EG001",
            name="CHU Test",
            short_name="CHU",
            physical_type="si",
            address_line1="1 rue Test"
        )
        memory_session.add(eg)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session)
        lines = message.split("\n")
        
        lch_lines = [l for l in lines if l.startswith("LCH|")]
        for lch_line in lch_lines:
            lch = parse_lch_fields(lch_line)
            assert lch["coding_system"] == "L", f"Coding system doit être L (local), trouvé: {lch['coding_system']} dans {lch_line}"
    
    def test_lrl_coding_system_local(self, memory_session):
        """Tous les codes LRL doivent utiliser le système local (^L)"""
        eg = EntiteGeographique(identifier="EG001", name="CHU", short_name="CHU", physical_type="si")
        memory_session.add(eg)
        memory_session.commit()
        memory_session.refresh(eg)
        
        pole = Pole(identifier="POLE001", name="Pôle", short_name="P", physical_type="wa", entite_geo_id=eg.id)
        memory_session.add(pole)
        memory_session.commit()
        
        message = generate_mfn_message(memory_session)
        lines = message.split("\n")
        
        lrl_lines = [l for l in lines if l.startswith("LRL|")]
        for lrl_line in lrl_lines:
            lrl = parse_lrl_fields(lrl_line)
            assert lrl["coding_system"] == "L", f"Coding system doit être L (local), trouvé: {lrl['coding_system']} dans {lrl_line}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
