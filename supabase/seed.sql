-- Seed 001 : Règles de catégorisation par défaut
-- Exécuter APRÈS la migration 003.
-- Ces règles couvrent les dépenses récurrentes les plus communes.

INSERT INTO categorization_rules (pattern, business_id, category, priority) VALUES

-- ---- Revenus pro --------------------------------------------------------
('virement phi',        'phi_rising',    'revenue', 100),
('coaching',            'phi_rising',    'revenue',  90),
('formation',           'phi_rising',    'revenue',  90),
('stripe',              'phi_rising',    'revenue',  80),
('photobooth',          'booth_in_lyon', 'revenue', 100),
('location booth',      'booth_in_lyon', 'revenue',  90),
('stripe',              'booth_in_lyon', 'revenue',  80),

-- ---- Frais pro communs (toutes activités) --------------------------------
('amazon',              NULL, 'office_supplies',  50),
('fnac',                NULL, 'office_supplies',  50),
('materiel',            NULL, 'office_supplies',  60),
('fournitures',         NULL, 'office_supplies',  70),
('abonnement',          NULL, 'software',         50),
('google',              NULL, 'software',         50),
('microsoft',           NULL, 'software',         50),
('notion',              NULL, 'software',         50),
('canva',               NULL, 'software',         50),
('ovh',                 NULL, 'software',         50),

-- ---- Transport -----------------------------------------------------------
('essence',             NULL, 'transport', 70),
('carburant',           NULL, 'transport', 70),
('sncf',                NULL, 'transport', 70),
('blablacar',           NULL, 'transport', 70),
('uber',                NULL, 'transport', 60),
('parking',             NULL, 'transport', 60),
('autoroute',           NULL, 'transport', 60),
('péage',               NULL, 'transport', 60),

-- ---- Budget perso --------------------------------------------------------
('loyer',               'personal', 'rent',       100),
('electricite',         'personal', 'utilities',   90),
('edf',                 'personal', 'utilities',   90),
('internet',            'personal', 'utilities',   80),
('orange',              'personal', 'utilities',   80),
('free',                'personal', 'utilities',   80),
('courses',             'personal', 'groceries',   80),
('leclerc',             'personal', 'groceries',   80),
('carrefour',           'personal', 'groceries',   80),
('lidl',                'personal', 'groceries',   80),
('restaurant',          'personal', 'meals',       70),
('cinema',              'personal', 'leisure',     70),
('netflix',             'personal', 'leisure',     80),
('spotify',             'personal', 'leisure',     80),
('epargne',             'personal', 'savings',    100),
('livret',              'personal', 'savings',    100),
('virement epargne',    'personal', 'savings',    100)

ON CONFLICT DO NOTHING;

-- Seed 002 : Taux URSSAF de référence
-- Source : urssaf.fr — mettre à jour chaque année.

-- Données 2024
-- Phi Rising   : BNC professions libérales (hors CIPAV) → 21.2 %
-- Booth in Lyon: BIC prestations de services            → 21.2 %
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

-- Seed 003 : Catégories par activité
-- Source : définitions métier fournies par l'utilisateur.
INSERT INTO categories (business_id, name, direction) VALUES
-- ---- Phi Rising — dépenses ------------------------------------------------
('phi_rising',    'Abonnement',         'expense'),
('phi_rising',    'Marketing',          'expense'),
('phi_rising',    'Prestataire',        'expense'),
('phi_rising',    'Formation / Autre',  'expense'),
-- ---- Phi Rising — revenus --------------------------------------------------
('phi_rising',    'BNC',                'income'),
('phi_rising',    'BIC',                'income'),
('phi_rising',    'Non déclaré',        'income'),
-- ---- Booth in Lyon — dépenses ----------------------------------------------
('booth_in_lyon', 'Consommable',        'expense'),
('booth_in_lyon', 'Pub',                'expense'),
('booth_in_lyon', 'Matériel',           'expense'),
('booth_in_lyon', 'Déplacement',        'expense'),
('booth_in_lyon', 'Abonnement',         'expense'),
('booth_in_lyon', 'Autre',              'expense'),
-- ---- Booth in Lyon — revenus -----------------------------------------------
('booth_in_lyon', 'Évenement Privé',    'income'),
('booth_in_lyon', 'Non déclaré',        'income'),
-- ---- Perso — dépenses ------------------------------------------------------
('personal',      'Loyer / Mensualité', 'expense'),
('personal',      'Epargne',            'expense'),
('personal',      'Abonnement',         'expense'),
('personal',      'Repas',              'expense'),
('personal',      'Médical',            'expense'),
('personal',      'Voyage',             'expense'),
('personal',      'Restau / Soirée',    'expense'),
('personal',      'Achats',             'expense'),
('personal',      'Autre Obligatoire',  'expense'),
('personal',      'Autre Loisir',       'expense')
ON CONFLICT (business_id, name, direction) DO NOTHING;

-- Seed 004 : Comptes réels du foyer
-- Exécuter APRÈS la migration 20260708120000_transaction_accounts.
INSERT INTO accounts (name, institution, type, owner, currency, balance) VALUES
    ('Compte pro coaching',   'Hello Bank', 'current', 'phi_rising',    'EUR', 0),
    ('Compte pro photobooth', 'Revolut',    'revolut', 'booth_in_lyon', 'EUR', 0),
    ('Compte perso',          'Boursobank', 'current', 'personal',      'EUR', 0),
    ('Compte commun',         'Hello Bank', 'current', 'personal',      'EUR', 0),
    ('Livret épargne',        'Boursobank', 'savings', 'personal',      'EUR', 0)
ON CONFLICT (name, owner) DO NOTHING;

-- Rattachement par défaut des transactions historiques (best-effort).
UPDATE transactions t
SET account_id = a.id
FROM accounts a
WHERE a.name = 'Compte pro coaching' AND a.owner = 'phi_rising'
  AND t.business_id = 'phi_rising' AND t.account_id IS NULL;

UPDATE transactions t
SET account_id = a.id
FROM accounts a
WHERE a.name = 'Compte pro photobooth' AND a.owner = 'booth_in_lyon'
  AND t.business_id = 'booth_in_lyon' AND t.account_id IS NULL;

UPDATE transactions t
SET account_id = a.id
FROM accounts a
WHERE a.name = 'Compte perso' AND a.owner = 'personal'
  AND t.business_id = 'personal' AND t.account_id IS NULL;
