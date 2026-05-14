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
