-- Migration 003 : Règles de catégorisation automatique

-- ---------------------------------------------------------------------------
-- Table : categorization_rules
-- Chaque règle associe un pattern (sous-chaîne du label) à une catégorie.
-- Plusieurs règles peuvent correspondre ; priority (DESC) détermine le gagnant.
-- ---------------------------------------------------------------------------
CREATE TABLE categorization_rules (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  timestamptz NOT NULL DEFAULT now(),
    pattern     text NOT NULL,             -- Sous-chaîne recherchée dans label (case-insensitive)
    business_id business_type,             -- NULL = s'applique à tous
    category    text NOT NULL,
    priority    integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    CONSTRAINT pattern_not_empty CHECK (length(trim(pattern)) > 0)
);

CREATE INDEX idx_rules_business_id ON categorization_rules (business_id);
CREATE INDEX idx_rules_priority    ON categorization_rules (priority DESC);
CREATE INDEX idx_rules_active      ON categorization_rules (is_active) WHERE is_active = true;

ALTER TABLE categorization_rules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON categorization_rules
    FOR ALL USING (true) WITH CHECK (true);
