-- Migration 005 : Table des taux URSSAF de référence

CREATE TABLE urssaf_rates (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id                 business_type NOT NULL,
    year                        integer NOT NULL,
    cotisations_rate            numeric(5, 4) NOT NULL,
    ca_threshold                numeric(10, 2) NOT NULL,
    tva_franchise_threshold     numeric(10, 2) NOT NULL,
    versement_liberatoire_rate  numeric(5, 4),
    UNIQUE (business_id, year)
);

ALTER TABLE urssaf_rates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON urssaf_rates
    FOR ALL USING (true) WITH CHECK (true);
