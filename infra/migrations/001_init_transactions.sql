-- Migration 001 : Table centrale des transactions
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor)

-- ---------------------------------------------------------------------------
-- Types ENUM partagés
-- ---------------------------------------------------------------------------
CREATE TYPE business_type AS ENUM (
    'phi_rising',
    'booth_in_lyon',
    'personal'
);

CREATE TYPE transaction_source AS ENUM (
    'bank',
    'stripe',
    'manual'
);

-- ---------------------------------------------------------------------------
-- Table : transactions
-- ---------------------------------------------------------------------------
CREATE TABLE transactions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    date            date NOT NULL,
    amount          numeric(12, 2) NOT NULL,
    label           text NOT NULL,
    source          transaction_source NOT NULL,
    business_id     business_type NOT NULL,
    category        text,
    is_income       boolean NOT NULL GENERATED ALWAYS AS (amount > 0) STORED,
    external_id     text UNIQUE,           -- ID bancaire ou Stripe pour déduplication
    notes           text,
    CONSTRAINT no_null_amount CHECK (amount IS NOT NULL)
);

-- Index pour les requêtes courantes
CREATE INDEX idx_transactions_business_id ON transactions (business_id);
CREATE INDEX idx_transactions_date        ON transactions (date DESC);
CREATE INDEX idx_transactions_category    ON transactions (category);
CREATE INDEX idx_transactions_source      ON transactions (source);
CREATE INDEX idx_transactions_business_date ON transactions (business_id, date DESC);

-- RLS : activer la sécurité au niveau ligne
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Politique provisoire : accès total (à restreindre si auth multi-utilisateur)
CREATE POLICY "allow_all_authenticated" ON transactions
    FOR ALL
    USING (true)
    WITH CHECK (true);
