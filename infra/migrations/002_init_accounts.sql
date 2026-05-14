-- Migration 002 : Comptes bancaires et épargne

CREATE TYPE account_type AS ENUM (
    'current',      -- Compte courant
    'savings',      -- Livret (A, LDDS…)
    'revolut',      -- Revolut (peut être multi-devises)
    'securities',   -- Compte-titres / PEA
    'cash'          -- Espèces
);

CREATE TYPE account_owner AS ENUM (
    'personal',     -- Foyer (budget perso)
    'phi_rising',   -- Compte pro Phi Rising
    'booth_in_lyon' -- Compte pro Booth in Lyon
);

-- ---------------------------------------------------------------------------
-- Table : accounts
-- ---------------------------------------------------------------------------
CREATE TABLE accounts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    name            text NOT NULL,
    institution     text,                   -- Ex : "Crédit Mutuel", "Revolut"
    type            account_type NOT NULL,
    owner           account_owner NOT NULL,
    currency        char(3) NOT NULL DEFAULT 'EUR',
    balance         numeric(14, 2) NOT NULL DEFAULT 0,
    last_synced_at  timestamptz,
    gocardless_id   text UNIQUE,            -- Référence GoCardless pour la synchro auto
    is_active       boolean NOT NULL DEFAULT true
);

CREATE INDEX idx_accounts_owner ON accounts (owner);
CREATE INDEX idx_accounts_type  ON accounts (type);

-- ---------------------------------------------------------------------------
-- Table : account_balance_history
-- Snapshot journalier du solde pour les courbes d'évolution patrimoniale
-- ---------------------------------------------------------------------------
CREATE TABLE account_balance_history (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    date        date NOT NULL,
    balance     numeric(14, 2) NOT NULL,
    UNIQUE (account_id, date)
);

CREATE INDEX idx_balance_history_account_date ON account_balance_history (account_id, date DESC);

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON accounts
    FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE account_balance_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON account_balance_history
    FOR ALL USING (true) WITH CHECK (true);
