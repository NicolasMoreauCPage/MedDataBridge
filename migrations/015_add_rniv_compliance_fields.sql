-- Migration 015: Ajout des champs de conformité RNIV (Référentiel National d'Identification)
-- Date: 2025-11-08
-- Description: Enrichissement du modèle Patient pour conformité complète INS/RNIV

-- 1. INS-C et type d'INS
ALTER TABLE patient ADD COLUMN ins_c TEXT;  -- INS Calculé (pour personnes sans NIR)
ALTER TABLE patient ADD COLUMN ins_type TEXT;  -- Type: "NIR" ou "INS-C"
ALTER TABLE patient ADD COLUMN ins_in_annuaire BOOLEAN DEFAULT FALSE;  -- INS-A (présent dans annuaire INSI)
ALTER TABLE patient ADD COLUMN ins_last_query_date TEXT;  -- Date dernier appel service INSI (AAAA-MM-JJ)

-- 2. Prénoms structurés selon RNIV
ALTER TABLE patient ADD COLUMN birth_given_names TEXT;  -- Liste complète prénoms état civil (séparés par espace)
ALTER TABLE patient ADD COLUMN used_given_name TEXT;  -- Prénom d'usage/usuel

-- 3. Code INSEE lieu de naissance
ALTER TABLE patient ADD COLUMN birth_insee_code TEXT;  -- Code INSEE 5 caractères (ou 2A/2B pour Corse)

-- 4. Matrice de Gestion d'Identité
ALTER TABLE patient ADD COLUMN identity_matrix_code TEXT;  -- Code MGI utilisée pour qualification

-- Indexes pour recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_patient_ins_c ON patient(ins_c) WHERE ins_c IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patient_ins_type ON patient(ins_type) WHERE ins_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patient_birth_insee ON patient(birth_insee_code) WHERE birth_insee_code IS NOT NULL;

-- Commentaires documentaires
COMMENT ON COLUMN patient.ins_c IS 'INS Calculé - Identifiant National de Santé pour personnes sans NIR (RNIV)';
COMMENT ON COLUMN patient.ins_type IS 'Type d''INS: "NIR" (Numéro Sécu) ou "INS-C" (Calculé) - RNIV';
COMMENT ON COLUMN patient.ins_in_annuaire IS 'INS-A: INS présent dans annuaire national INSI (TéléSanté) - RNIV';
COMMENT ON COLUMN patient.ins_last_query_date IS 'Date dernier appel service INSI pour vérification INS - RNIV';
COMMENT ON COLUMN patient.birth_given_names IS 'Liste complète prénoms état civil (ordre officiel, séparés espaces) - RNIV Trait Strict';
COMMENT ON COLUMN patient.used_given_name IS 'Prénom d''usage/usuel (peut différer du 1er prénom état civil) - RNIV';
COMMENT ON COLUMN patient.birth_insee_code IS 'Code INSEE lieu naissance (5 chars: ex 75056 Paris, 2A004 Ajaccio) - RNIV Trait Strict';
COMMENT ON COLUMN patient.identity_matrix_code IS 'Code Matrice de Gestion d''Identité utilisée pour qualification - RNIV';

-- Note: identity_reliability_code devrait être contraint aux valeurs RNIV:
-- VALI (Validée), QUAL (Qualifiée), PROV (Provisoire), VIDE (Fictive), DOUTE (Douteuse), DOUB (Doublon)
-- Pour l'instant reste TEXT pour compatibilité avec valeurs HL7 existantes (VIDE/PROV/VALI/DOUTE/FICTI)
