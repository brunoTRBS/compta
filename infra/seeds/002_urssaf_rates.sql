-- Seed 002 : Taux URSSAF de référence
-- Exécuter APRÈS la migration 001.
-- Source : urssaf.fr — mettre à jour chaque année.

-- ---------------------------------------------------------------------------
-- Table de référence (créée ici pour garder le schéma dans les migrations)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS urssaf_rates (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id                 business_type NOT NULL,
    year                        integer NOT NULL,
    cotisations_rate            numeric(5, 4) NOT NULL,  -- Taux cotisations sociales
    ca_threshold                numeric(10, 2) NOT NULL, -- Plafond CA micro-entreprise
    tva_franchise_threshold     numeric(10, 2) NOT NULL, -- Seuil franchise TVA
    versement_liberatoire_rate  numeric(5, 4),           -- NULL si option non choisie
    UNIQUE (business_id, year)
);

ALTER TABLE urssaf_rates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON urssaf_rates
    FOR ALL USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Données 2024
-- Phi Rising   : BNC professions libérales (hors CIPAV) → 21.2 %
-- Booth in Lyon: BIC prestations de services            → 21.2 %
--
-- ATTENTION : vérifier si Booth in Lyon est classé BIC commerce (12.3 %)
-- selon le code APE déclaré auprès de l'URSSAF.
-- ---------------------------------------------------------------------------
INSERT INTO urssaf_rates
    (business_id, year, cotisations_rate, ca_threshold, tva_franchise_threshold, versement_liberatoire_rate)
VALUES
    ('phi_rising',    2024, 0.2120, 77700.00, 36800.00, 0.0220),
    ('booth_in_lyon', 2024, 0.2120, 77700.00, 36800.00, 0.0170)
ON CONFLICT (business_id, year) DO UPDATE
    SET cotisations_rate           = EXCLUDED.cotisations_rate,
        ca_threshold               = EXCLUDED.ca_threshold,
        tva_franchise_threshold    = EXCLUDED.tva_franchise_threshold,
        versement_liberatoire_rate = EXCLUDED.versement_liberatoire_rate;

-- Données 2025 (à confirmer après publication officielle)
INSERT INTO urssaf_rates
    (business_id, year, cotisations_rate, ca_threshold, tva_franchise_threshold, versement_liberatoire_rate)
VALUES
    ('phi_rising',    2025, 0.2120, 77700.00, 37500.00, 0.0220),
    ('booth_in_lyon', 2025, 0.2120, 77700.00, 37500.00, 0.0170)
ON CONFLICT (business_id, year) DO UPDATE
    SET cotisations_rate           = EXCLUDED.cotisations_rate,
        ca_threshold               = EXCLUDED.ca_threshold,
        tva_franchise_threshold    = EXCLUDED.tva_franchise_threshold,
        versement_liberatoire_rate = EXCLUDED.versement_liberatoire_rate;
