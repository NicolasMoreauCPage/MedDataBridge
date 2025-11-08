-- Migration 014: ZBE compliance additions
-- Adds columns required for full IHE PAM FR ZBE support and movement nature/action semantics.
-- Columns: action, is_historic, original_trigger, nature, uf_medicale_code, uf_medicale_label,
--          uf_soins_code, uf_soins_label, movement_ids (JSON array textual),
--          plus indexes for common query patterns.

ALTER TABLE mouvement ADD COLUMN action TEXT;                -- INSERT|UPDATE|CANCEL
ALTER TABLE mouvement ADD COLUMN is_historic BOOLEAN DEFAULT FALSE; -- ZBE-5 flag
ALTER TABLE mouvement ADD COLUMN original_trigger TEXT;       -- ZBE-6 trigger original
ALTER TABLE mouvement ADD COLUMN nature TEXT;                 -- ZBE-9 nature code (S,H,M,L,D,SM)
ALTER TABLE mouvement ADD COLUMN uf_medicale_code TEXT;       -- XON component 10 from ZBE-7
ALTER TABLE mouvement ADD COLUMN uf_medicale_label TEXT;      -- XON component 1 from ZBE-7
ALTER TABLE mouvement ADD COLUMN uf_soins_code TEXT;          -- XON component 10 from ZBE-8
ALTER TABLE mouvement ADD COLUMN uf_soins_label TEXT;         -- XON component 1 from ZBE-8
ALTER TABLE mouvement ADD COLUMN movement_ids TEXT;           -- JSON array of all ZBE-1 identifiers if repetition

-- Basic indexes (tune later if needed)
CREATE INDEX IF NOT EXISTS idx_mouvement_action ON mouvement(action);
CREATE INDEX IF NOT EXISTS idx_mouvement_nature ON mouvement(nature);
CREATE INDEX IF NOT EXISTS idx_mouvement_uf_medicale_code ON mouvement(uf_medicale_code);
CREATE INDEX IF NOT EXISTS idx_mouvement_uf_soins_code ON mouvement(uf_soins_code);
CREATE INDEX IF NOT EXISTS idx_mouvement_action_nature ON mouvement(action, nature);
