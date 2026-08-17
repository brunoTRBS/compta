-- Migration 007 : Transactions récurrentes
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 006.
--
-- Un modèle de récurrence (loyer, abonnement, salaire...) qu'on valide chaque mois
-- depuis Saisie > Récurrences au lieu de tout retaper. last_materialized_year/month
-- retient le dernier mois déjà validé pour ce modèle, afin de ne le proposer qu'une
-- fois par mois.

CREATE TABLE recurring_transactions (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at               timestamptz NOT NULL DEFAULT now(),
    label                    text NOT NULL,
    amount                   numeric(12, 2) NOT NULL,  -- signé : négatif = dépense, positif = revenu
    category                 text,
    business_id              business_type NOT NULL,
    account_id               uuid REFERENCES accounts(id),
    day_of_month             integer NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    is_active                boolean NOT NULL DEFAULT true,
    last_materialized_year   integer,
    last_materialized_month  integer,
    notes                    text,
    CONSTRAINT no_zero_amount CHECK (amount != 0)
);

CREATE INDEX idx_recurring_active ON recurring_transactions (is_active) WHERE is_active = true;

ALTER TABLE recurring_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner_only" ON recurring_transactions
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));
