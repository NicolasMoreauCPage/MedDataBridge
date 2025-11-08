-- Migration 013: Ajout des champs UF au modèle Dossier
-- Date: 2025-11-08
-- Permet de tracker séparément les 3 types d'UF (médicale, hébergement, soins)

ALTER TABLE dossier ADD COLUMN uf_medicale TEXT;
ALTER TABLE dossier ADD COLUMN uf_hebergement TEXT;
ALTER TABLE dossier ADD COLUMN uf_soins TEXT;

CREATE INDEX IF NOT EXISTS idx_dossier_uf_medicale ON dossier(uf_medicale);
CREATE INDEX IF NOT EXISTS idx_dossier_uf_hebergement ON dossier(uf_hebergement);
CREATE INDEX IF NOT EXISTS idx_dossier_uf_soins ON dossier(uf_soins);
