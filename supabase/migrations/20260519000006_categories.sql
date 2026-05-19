-- Migration 006 : Table des catégories de transactions
-- Remplace les constantes hardcodées dans config.py.
-- Gérée depuis l'onglet Paramètres de l'app.

CREATE TABLE categories (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  timestamptz NOT NULL DEFAULT now(),
    business_id text NOT NULL,
    name        text NOT NULL,
    direction   text NOT NULL CHECK (direction IN ('income', 'expense')),
    UNIQUE (business_id, name, direction)
);

CREATE INDEX idx_categories_business_id ON categories (business_id);
CREATE INDEX idx_categories_direction   ON categories (direction);

ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON categories
    FOR ALL
    USING (true)
    WITH CHECK (true);
