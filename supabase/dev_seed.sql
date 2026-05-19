-- =============================================================
-- DEV SEED — Données de démonstration pour test manuel en local
-- =============================================================
-- NE PAS EXÉCUTER EN PRODUCTION.
--
-- Exécution (après avoir appliqué seed.sql) :
--   cat supabase/dev_seed.sql | docker exec -i supabase_db_compta psql -U postgres -d postgres
--
-- Nettoyage complet :
--   TRUNCATE transactions, account_balance_history, accounts RESTART IDENTITY CASCADE;
--
-- Catégories utilisées (doivent exister dans la table categories via seed.sql) :
--   Phi Rising    revenus  → BNC, Non déclaré
--   Phi Rising    dépenses → Abonnement, Marketing, Prestataire, Formation / Autre
--   Booth in Lyon revenus  → Évenement Privé, Non déclaré
--   Booth in Lyon dépenses → Consommable, Pub, Matériel, Déplacement, Abonnement, Autre
--   Perso         revenus  → NULL (aucune catégorie revenu définie)
--   Perso         dépenses → Loyer / Mensualité, Epargne, Abonnement, Repas, Médical,
--                            Voyage, Restau / Soirée, Achats, Autre Obligatoire, Autre Loisir
-- =============================================================

-- =============================================================
-- 1. COMPTES
-- =============================================================
INSERT INTO accounts (id, name, institution, type, owner, currency, balance, last_synced_at)
VALUES
  ('00000000-0000-0000-0001-000000000001', 'Compte Courant',           'Crédit Mutuel', 'current',    'personal',      'EUR',  3250.00, now()),
  ('00000000-0000-0000-0001-000000000002', 'Livret A',                 'Crédit Mutuel', 'savings',    'personal',      'EUR',  8500.00, now()),
  ('00000000-0000-0000-0001-000000000003', 'LDDS',                     'Crédit Mutuel', 'savings',    'personal',      'EUR',  4200.00, now()),
  ('00000000-0000-0000-0001-000000000004', 'PEA',                      'Boursorama',    'securities', 'personal',      'EUR', 15800.00, now()),
  ('00000000-0000-0000-0001-000000000005', 'Revolut',                  'Revolut',       'revolut',    'personal',      'EUR',   620.00, now()),
  ('00000000-0000-0000-0001-000000000006', 'Compte Pro Phi Rising',    'Qonto',         'current',    'phi_rising',    'EUR',  4100.00, now()),
  ('00000000-0000-0000-0001-000000000007', 'Compte Pro Booth in Lyon', 'Qonto',         'current',    'booth_in_lyon', 'EUR',  2800.00, now())
ON CONFLICT (id) DO NOTHING;

-- =============================================================
-- 2. HISTORIQUE DES SOLDES (jan 2025 → mai 2026, n = 0..16)
-- =============================================================
INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000001'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (ARRAY[2200,2450,2800,2600,3100,2900,2500,2300,2700,3000,3200,3000,
              3250,3100,3400,3200,3250]::numeric[])[n+1]
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000002'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (6500 + n * 125)::numeric
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000003'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (1800 + n * 150)::numeric
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000004'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (ARRAY[10000,10200,10650,11200,11800,12100,11900,12500,13100,13800,14200,14500,
              14800,15000,15400,15600,15800]::numeric[])[n+1]
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000005'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (ARRAY[400,550,350,620,480,700,800,650,420,590,480,750,
              620,500,680,590,620]::numeric[])[n+1]
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000006'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (ARRAY[2000,3500,2800,4200,3800,3000,2500,2000,3500,4200,3800,3500,
              4100,3500,3000,4200,4100]::numeric[])[n+1]
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

INSERT INTO account_balance_history (account_id, date, balance)
SELECT '00000000-0000-0000-0001-000000000007'::uuid,
       ('2025-01-01'::date + (interval '1 month' * n))::date,
       (ARRAY[1500,2000,2800,3500,3000,2500,2000,1800,2200,2800,2500,2000,
              2800,2200,3000,2800,2800]::numeric[])[n+1]
FROM generate_series(0, 16) n ON CONFLICT (account_id, date) DO NOTHING;

-- =============================================================
-- 3. TRANSACTIONS — Phi Rising (coaching / formation BNC)
--    Revenus  → "BNC"
--    Dépenses → "Abonnement", "Marketing", "Prestataire", "Formation / Autre"
-- =============================================================
INSERT INTO transactions (date, amount, label, source, business_id, category, external_id) VALUES
  -- 2025
  ('2025-01-15',  1800.00, 'Coaching individuel — client M.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-01-01'),
  ('2025-01-28',  -120.00, 'Notion + Canva Pro (jan)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-01-02'),
  ('2025-02-10',  2200.00, 'Coaching individuel — client S.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-02-01'),
  ('2025-02-20',  1500.00, 'Formation leadership groupe',            'bank',   'phi_rising', 'BNC',               'dev:phi:2025-02-02'),
  ('2025-02-25',  -350.00, 'Graphiste — refonte supports visuels',   'bank',   'phi_rising', 'Prestataire',       'dev:phi:2025-02-03'),
  ('2025-03-05',  2500.00, 'Coaching individuel — client P.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-03-01'),
  ('2025-03-18',  2000.00, 'Formation management 2 jours',           'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-03-02'),
  ('2025-03-22',  -180.00, 'Livres pédagogiques FNAC',               'bank',   'phi_rising', 'Formation / Autre', 'dev:phi:2025-03-03'),
  ('2025-03-28',   -90.00, 'Google Workspace (mar)',                 'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-03-04'),
  ('2025-04-08',  1800.00, 'Coaching individuel — client A.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-04-01'),
  ('2025-04-12',  3000.00, 'Formation communication 3 jours',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-04-02'),
  ('2025-04-20',  -250.00, 'Campagne LinkedIn Ads (avr)',            'manual', 'phi_rising', 'Marketing',         'dev:phi:2025-04-03'),
  ('2025-05-14',  2200.00, 'Coaching individuel — client B.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-05-01'),
  ('2025-05-20',  -120.00, 'Notion + Canva Pro (mai)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-05-02'),
  ('2025-05-28',   -65.00, 'Déplacement Lyon–Paris (SNCF)',          'bank',   'phi_rising', 'Formation / Autre', 'dev:phi:2025-05-03'),
  ('2025-06-03',  1500.00, 'Coaching individuel — client C.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-06-01'),
  ('2025-06-17',  1200.00, 'Atelier prise de parole',                'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-06-02'),
  ('2025-06-25',  -100.00, 'OVH hébergement annuel',                 'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-06-03'),
  ('2025-06-28',  -400.00, 'Comptable — bilan semestriel',           'bank',   'phi_rising', 'Prestataire',       'dev:phi:2025-06-04'),
  ('2025-07-10',   800.00, 'Coaching individuel — client M.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-07-01'),
  ('2025-08-20',   600.00, 'Coaching en ligne — client S.',          'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-08-01'),
  ('2025-08-25',  -300.00, 'Campagne Meta Ads (août)',               'manual', 'phi_rising', 'Marketing',         'dev:phi:2025-08-02'),
  ('2025-09-02',  2500.00, 'Coaching individuel — client D.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-09-01'),
  ('2025-09-15',  2500.00, 'Formation leadership rentrée',           'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-09-02'),
  ('2025-09-28',  -250.00, 'Matériel pédagogique FNAC',              'bank',   'phi_rising', 'Formation / Autre', 'dev:phi:2025-09-03'),
  ('2025-10-07',  3000.00, 'Coaching individuel — client L.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-10-01'),
  ('2025-10-20',  1500.00, 'Atelier communication entreprise',       'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-10-02'),
  ('2025-10-25',  -120.00, 'Notion + Canva Pro (oct)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-10-03'),
  ('2025-10-30',  -500.00, 'Designer freelance — slides formation',  'bank',   'phi_rising', 'Prestataire',       'dev:phi:2025-10-04'),
  ('2025-11-11',  2000.00, 'Coaching individuel — client R.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-11-01'),
  ('2025-11-25',  2000.00, 'Formation transitions professionnelles', 'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-11-02'),
  ('2025-11-28',   -90.00, 'Google Workspace (nov)',                 'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-11-03'),
  ('2025-12-09',  1500.00, 'Coaching bilan annuel — client M.',      'stripe', 'phi_rising', 'BNC',               'dev:phi:2025-12-01'),
  ('2025-12-15',  -350.00, 'Campagne Google Ads (déc)',              'manual', 'phi_rising', 'Marketing',         'dev:phi:2025-12-02'),
  ('2025-12-20',  -120.00, 'Notion + Canva Pro (déc)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2025-12-03'),
  -- 2026
  ('2026-01-13',  2200.00, 'Coaching individuel — client S.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-01-01'),
  ('2026-01-27',  1500.00, 'Formation leadership groupe',            'bank',   'phi_rising', 'BNC',               'dev:phi:2026-01-02'),
  ('2026-01-28',  -120.00, 'Notion + Canva Pro (jan)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2026-01-03'),
  ('2026-02-10',  2800.00, 'Coaching individuel — client P.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-02-01'),
  ('2026-02-15',  -450.00, 'Comptable — déclaration URSSAF',         'bank',   'phi_rising', 'Prestataire',       'dev:phi:2026-02-02'),
  ('2026-02-20',   -90.00, 'Google Workspace (fév)',                 'manual', 'phi_rising', 'Abonnement',        'dev:phi:2026-02-03'),
  ('2026-03-04',  3000.00, 'Coaching individuel — client A.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-03-01'),
  ('2026-03-18',  2500.00, 'Formation management avancé',            'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-03-02'),
  ('2026-03-25',  -280.00, 'Campagne LinkedIn Ads (mar)',            'manual', 'phi_rising', 'Marketing',         'dev:phi:2026-03-03'),
  ('2026-04-08',  2000.00, 'Coaching individuel — client D.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-04-01'),
  ('2026-04-22',  1800.00, 'Atelier leadership entreprise',          'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-04-02'),
  ('2026-04-25',  -200.00, 'Livres & ressources pédagogiques',       'bank',   'phi_rising', 'Formation / Autre', 'dev:phi:2026-04-03'),
  ('2026-04-28',  -120.00, 'Notion + Canva Pro (avr)',               'manual', 'phi_rising', 'Abonnement',        'dev:phi:2026-04-04'),
  ('2026-05-06',  1500.00, 'Coaching individuel — client L.',        'stripe', 'phi_rising', 'BNC',               'dev:phi:2026-05-01'),
  ('2026-05-15',   -90.00, 'Google Workspace (mai)',                 'manual', 'phi_rising', 'Abonnement',        'dev:phi:2026-05-02')
ON CONFLICT (external_id) DO NOTHING;

-- =============================================================
-- 4. TRANSACTIONS — Booth in Lyon (location photobooth BIC)
--    Revenus  → "Évenement Privé", "Non déclaré"
--    Dépenses → "Consommable", "Pub", "Matériel", "Déplacement", "Abonnement", "Autre"
-- =============================================================
INSERT INTO transactions (date, amount, label, source, business_id, category, external_id) VALUES
  -- 2025
  ('2025-01-18',   800.00, 'Location photobooth mariage — Lyon',             'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-01-01'),
  ('2025-01-30',   -90.00, 'Papier photo + cartouches (jan)',                 'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2025-01-02'),
  ('2025-02-08',  1500.00, 'Location photobooth soirée Saint-Valentin',       'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-02-01'),
  ('2025-02-22',  1200.00, 'Location photobooth anniversaire — Lyon',         'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-02-02'),
  ('2025-02-28',  -150.00, 'Campagne Instagram Ads (fév)',                    'manual', 'booth_in_lyon', 'Pub',             'dev:booth:2025-02-03'),
  ('2025-03-01',  2500.00, 'Location photobooth mariage — Villeurbanne',      'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-03-01'),
  ('2025-03-15',  2000.00, 'Location photobooth séminaire entreprise',        'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-03-02'),
  ('2025-03-20',  -200.00, 'Carburant + péage A46 — déplacement',             'bank',   'booth_in_lyon', 'Déplacement',     'dev:booth:2025-03-03'),
  ('2025-03-25',  -120.00, 'Papier photo + cartouches (mar)',                 'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2025-03-04'),
  ('2025-04-05',  3000.00, 'Location photobooth mariage — Annecy',            'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-04-01'),
  ('2025-04-19',  2000.00, 'Location photobooth soirée gala',                 'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-04-02'),
  ('2025-04-28',  -200.00, 'Campagne Facebook Ads (avr)',                     'manual', 'booth_in_lyon', 'Pub',             'dev:booth:2025-04-03'),
  ('2025-05-03',  2500.00, 'Location photobooth mariage — Grenoble',          'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-05-01'),
  ('2025-05-17',  1500.00, 'Location photobooth anniversaire 18 ans',         'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-05-02'),
  ('2025-05-25',  -300.00, 'Accessoires décoration photobooth Amazon',        'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2025-05-03'),
  ('2025-05-28',   -50.00, 'Logiciel Dslrbooth — abonnement mensuel',         'manual', 'booth_in_lyon', 'Abonnement',      'dev:booth:2025-05-04'),
  ('2025-06-07',  3000.00, 'Location photobooth mariage — Lyon',              'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-06-01'),
  ('2025-06-21',  1500.00, 'Location photobooth soirée entreprise',           'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-06-02'),
  ('2025-06-25',  -180.00, 'Carburant + parking — déplacements juin',         'bank',   'booth_in_lyon', 'Déplacement',     'dev:booth:2025-06-03'),
  ('2025-07-12',  2500.00, 'Location photobooth festival Lyon',               'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-07-01'),
  ('2025-07-26',  1000.00, 'Location photobooth mariage été',                 'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-07-02'),
  ('2025-07-30',  -500.00, 'Réparation imprimante photobooth',                'bank',   'booth_in_lyon', 'Matériel',        'dev:booth:2025-07-03'),
  ('2025-08-16',  1500.00, 'Location photobooth soirée privée',               'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-08-01'),
  ('2025-08-20',   500.00, 'Location photobooth pool party — espèces',        'manual', 'booth_in_lyon', 'Non déclaré',     'dev:booth:2025-08-02'),
  ('2025-08-25',  -150.00, 'Campagne Instagram Ads (août)',                   'manual', 'booth_in_lyon', 'Pub',             'dev:booth:2025-08-03'),
  ('2025-09-06',  2000.00, 'Location photobooth séminaire rentrée',           'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-09-01'),
  ('2025-09-20',  1000.00, 'Location photobooth mariage',                     'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-09-02'),
  ('2025-09-28',  -180.00, 'Carburant + péage — déplacement Clermont',        'bank',   'booth_in_lyon', 'Déplacement',     'dev:booth:2025-09-03'),
  ('2025-10-04',  3000.00, 'Location photobooth mariage — Clermont-Fd',       'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-10-01'),
  ('2025-10-18',  1500.00, 'Location photobooth gala associations',           'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-10-02'),
  ('2025-10-25',  -120.00, 'Papier photo + cartouches (oct)',                 'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2025-10-03'),
  ('2025-10-28',  -200.00, 'Campagne Facebook Ads (oct)',                     'manual', 'booth_in_lyon', 'Pub',             'dev:booth:2025-10-04'),
  ('2025-11-15',  1800.00, 'Location photobooth soirée entreprise',           'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-11-01'),
  ('2025-11-20',   -50.00, 'Logiciel Dslrbooth — abonnement mensuel',         'manual', 'booth_in_lyon', 'Abonnement',      'dev:booth:2025-11-02'),
  ('2025-12-06',  2000.00, 'Location photobooth soirée Noël entreprise',      'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2025-12-01'),
  ('2025-12-20',  1000.00, 'Location photobooth réveillon — espèces',         'manual', 'booth_in_lyon', 'Non déclaré',     'dev:booth:2025-12-02'),
  ('2025-12-22',  -120.00, 'Papier photo + cartouches (déc)',                 'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2025-12-03'),
  -- 2026
  ('2026-01-25',  1000.00, 'Location photobooth soirée galette',              'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-01-01'),
  ('2026-01-30',   -50.00, 'Logiciel Dslrbooth — abonnement mensuel',         'manual', 'booth_in_lyon', 'Abonnement',      'dev:booth:2026-01-02'),
  ('2026-02-08',  1500.00, 'Location photobooth Saint-Valentin',              'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-02-01'),
  ('2026-02-15',  -800.00, 'Nouvel écran photobooth tactile',                 'bank',   'booth_in_lyon', 'Matériel',        'dev:booth:2026-02-02'),
  ('2026-02-20',  -150.00, 'Carburant — déplacement Genève',                  'bank',   'booth_in_lyon', 'Déplacement',     'dev:booth:2026-02-03'),
  ('2026-03-07',  2500.00, 'Location photobooth mariage — Lyon',              'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-03-01'),
  ('2026-03-22',  2000.00, 'Location photobooth séminaire',                   'bank',   'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-03-02'),
  ('2026-03-28',  -200.00, 'Papier impression + accessoires (mar)',           'bank',   'booth_in_lyon', 'Consommable',     'dev:booth:2026-03-03'),
  ('2026-04-12',  2000.00, 'Location photobooth mariage — Annecy',            'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-04-01'),
  ('2026-04-26',  -150.00, 'Campagne Instagram Ads (avr)',                    'manual', 'booth_in_lyon', 'Pub',             'dev:booth:2026-04-02'),
  ('2026-04-28',   -50.00, 'Logiciel Dslrbooth — abonnement mensuel',         'manual', 'booth_in_lyon', 'Abonnement',      'dev:booth:2026-04-03'),
  ('2026-05-10',  1500.00, 'Location photobooth mariage — Bourg-en-Bresse',   'stripe', 'booth_in_lyon', 'Évenement Privé', 'dev:booth:2026-05-01'),
  ('2026-05-17',  -160.00, 'Carburant + péage — déplacements mai',            'bank',   'booth_in_lyon', 'Déplacement',     'dev:booth:2026-05-02')
ON CONFLICT (external_id) DO NOTHING;

-- =============================================================
-- 5. TRANSACTIONS — Budget Personnel
--    Revenus  → NULL (aucune catégorie revenu définie pour perso)
--    Dépenses → catégories françaises (voir liste en en-tête)
--    ~10 transactions NULL disséminées pour tester la catégorisation
-- =============================================================
INSERT INTO transactions (date, amount, label, source, business_id, category, external_id) VALUES
  -- Janvier 2025
  ('2025-01-02',  1500.00, 'Virement Phi Rising jan',        'manual', 'personal', NULL,                  'dev:perso:2025-01-01'),
  ('2025-01-02',   900.00, 'Virement Booth jan',             'manual', 'personal', NULL,                  'dev:perso:2025-01-02'),
  ('2025-01-05',  -900.00, 'Loyer janvier',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-01-03'),
  ('2025-01-06',   -80.00, 'EDF janvier',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-01-04'),
  ('2025-01-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-01-05'),
  ('2025-01-12',  -380.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2025-01-06'),
  ('2025-01-18',   -85.00, 'Restaurant Le Bouchon',          'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-01-07'),
  ('2025-01-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-01-08'),
  ('2025-01-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-01-09'),
  ('2025-01-25',  -200.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-01-10'),
  ('2025-01-28',   -47.00, 'Achat en ligne 2801',            'bank',   'personal', NULL,                  'dev:perso:2025-01-11'),

  -- Février 2025
  ('2025-02-02',  1800.00, 'Virement Phi Rising fév',        'manual', 'personal', NULL,                  'dev:perso:2025-02-01'),
  ('2025-02-02',  1000.00, 'Virement Booth fév',             'manual', 'personal', NULL,                  'dev:perso:2025-02-02'),
  ('2025-02-05',  -900.00, 'Loyer février',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-02-03'),
  ('2025-02-06',   -80.00, 'EDF février',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-02-04'),
  ('2025-02-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-02-05'),
  ('2025-02-14',  -410.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2025-02-06'),
  ('2025-02-15',   -60.00, 'Restaurant Saint-Valentin',      'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-02-07'),
  ('2025-02-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-02-08'),
  ('2025-02-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-02-09'),
  ('2025-02-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-02-10'),

  -- Mars 2025
  ('2025-03-02',  2000.00, 'Virement Phi Rising mar',        'manual', 'personal', NULL,                  'dev:perso:2025-03-01'),
  ('2025-03-02',  1200.00, 'Virement Booth mar',             'manual', 'personal', NULL,                  'dev:perso:2025-03-02'),
  ('2025-03-05',  -900.00, 'Loyer mars',                     'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-03-03'),
  ('2025-03-06',   -80.00, 'EDF mars',                       'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-03-04'),
  ('2025-03-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-03-05'),
  ('2025-03-10',  -420.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2025-03-06'),
  ('2025-03-15',   -35.00, 'Pharmacie',                      'bank',   'personal', 'Médical',             'dev:perso:2025-03-07'),
  ('2025-03-20',  -100.00, 'Restaurant brasserie + soirée',  'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-03-08'),
  ('2025-03-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-03-09'),
  ('2025-03-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-03-10'),
  ('2025-03-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-03-11'),
  ('2025-03-27',   -68.00, 'CB ONLINE PAYMENT 2703',         'bank',   'personal', NULL,                  'dev:perso:2025-03-12'),

  -- Avril 2025
  ('2025-04-02',  2000.00, 'Virement Phi Rising avr',        'manual', 'personal', NULL,                  'dev:perso:2025-04-01'),
  ('2025-04-02',  1500.00, 'Virement Booth avr',             'manual', 'personal', NULL,                  'dev:perso:2025-04-02'),
  ('2025-04-05',  -900.00, 'Loyer avril',                    'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-04-03'),
  ('2025-04-06',   -80.00, 'EDF avril',                      'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-04-04'),
  ('2025-04-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-04-05'),
  ('2025-04-12',  -395.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2025-04-06'),
  ('2025-04-18',   -75.00, 'Restaurant bistrot',             'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-04-07'),
  ('2025-04-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-04-08'),
  ('2025-04-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-04-09'),
  ('2025-04-25',  -400.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-04-10'),
  ('2025-04-28',   -89.00, 'Amazon — achat divers',          'bank',   'personal', 'Achats',              'dev:perso:2025-04-11'),

  -- Mai 2025
  ('2025-05-02',  1800.00, 'Virement Phi Rising mai',        'manual', 'personal', NULL,                  'dev:perso:2025-05-01'),
  ('2025-05-02',  1200.00, 'Virement Booth mai',             'manual', 'personal', NULL,                  'dev:perso:2025-05-02'),
  ('2025-05-05',  -900.00, 'Loyer mai',                      'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-05-03'),
  ('2025-05-06',   -80.00, 'EDF mai',                        'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-05-04'),
  ('2025-05-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-05-05'),
  ('2025-05-14',  -450.00, 'Courses Lidl + Leclerc',         'bank',   'personal', 'Repas',               'dev:perso:2025-05-06'),
  ('2025-05-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-05-07'),
  ('2025-05-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-05-08'),
  ('2025-05-25',  -200.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-05-09'),
  ('2025-05-28',  -120.00, 'VIRT RECU REMB AMI',             'bank',   'personal', NULL,                  'dev:perso:2025-05-10'),

  -- Juin 2025
  ('2025-06-02',  1600.00, 'Virement Phi Rising jun',        'manual', 'personal', NULL,                  'dev:perso:2025-06-01'),
  ('2025-06-02',  1200.00, 'Virement Booth jun',             'manual', 'personal', NULL,                  'dev:perso:2025-06-02'),
  ('2025-06-05',  -900.00, 'Loyer juin',                     'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-06-03'),
  ('2025-06-06',   -80.00, 'EDF juin',                       'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-06-04'),
  ('2025-06-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-06-05'),
  ('2025-06-12',  -380.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2025-06-06'),
  ('2025-06-14',   -55.00, 'Soirée bar — Lyon 7e',           'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-06-07'),
  ('2025-06-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-06-08'),
  ('2025-06-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-06-09'),
  ('2025-06-25',  -200.00, 'Virement épargne LDDS',          'bank',   'personal', 'Epargne',             'dev:perso:2025-06-10'),

  -- Juillet 2025
  ('2025-07-02',  1200.00, 'Virement Phi Rising jul',        'manual', 'personal', NULL,                  'dev:perso:2025-07-01'),
  ('2025-07-02',  1000.00, 'Virement Booth jul',             'manual', 'personal', NULL,                  'dev:perso:2025-07-02'),
  ('2025-07-05',  -900.00, 'Loyer juillet',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-07-03'),
  ('2025-07-06',   -80.00, 'EDF juillet',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-07-04'),
  ('2025-07-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-07-05'),
  ('2025-07-10',  -420.00, 'Courses vacances',               'bank',   'personal', 'Repas',               'dev:perso:2025-07-06'),
  ('2025-07-12',  -650.00, 'Billet train + hôtel — vacances','bank',   'personal', 'Voyage',              'dev:perso:2025-07-07'),
  ('2025-07-15',  -180.00, 'Restaurants vacances',           'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-07-08'),
  ('2025-07-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-07-09'),
  ('2025-07-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-07-10'),

  -- Août 2025
  ('2025-08-02',  1000.00, 'Virement Phi Rising aoû',        'manual', 'personal', NULL,                  'dev:perso:2025-08-01'),
  ('2025-08-02',   800.00, 'Virement Booth aoû',             'manual', 'personal', NULL,                  'dev:perso:2025-08-02'),
  ('2025-08-05',  -900.00, 'Loyer août',                     'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-08-03'),
  ('2025-08-06',   -80.00, 'EDF août',                       'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-08-04'),
  ('2025-08-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-08-05'),
  ('2025-08-10',  -350.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2025-08-06'),
  ('2025-08-15',  -480.00, 'Vol + airbnb — week-end Barcelone','bank', 'personal', 'Voyage',              'dev:perso:2025-08-07'),
  ('2025-08-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-08-08'),
  ('2025-08-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-08-09'),
  ('2025-08-28',   -89.00, 'Amazon — vêtements rentrée',     'bank',   'personal', 'Achats',              'dev:perso:2025-08-10'),

  -- Septembre 2025
  ('2025-09-02',  2000.00, 'Virement Phi Rising sep',        'manual', 'personal', NULL,                  'dev:perso:2025-09-01'),
  ('2025-09-02',  1200.00, 'Virement Booth sep',             'manual', 'personal', NULL,                  'dev:perso:2025-09-02'),
  ('2025-09-05',  -900.00, 'Loyer septembre',                'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-09-03'),
  ('2025-09-06',   -80.00, 'EDF septembre',                  'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-09-04'),
  ('2025-09-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-09-05'),
  ('2025-09-10',  -400.00, 'Courses Leclerc rentrée',        'bank',   'personal', 'Repas',               'dev:perso:2025-09-06'),
  ('2025-09-12',   -45.00, 'Médecin généraliste',            'bank',   'personal', 'Médical',             'dev:perso:2025-09-07'),
  ('2025-09-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-09-08'),
  ('2025-09-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-09-09'),
  ('2025-09-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-09-10'),

  -- Octobre 2025
  ('2025-10-02',  2000.00, 'Virement Phi Rising oct',        'manual', 'personal', NULL,                  'dev:perso:2025-10-01'),
  ('2025-10-02',  1500.00, 'Virement Booth oct',             'manual', 'personal', NULL,                  'dev:perso:2025-10-02'),
  ('2025-10-05',  -900.00, 'Loyer octobre',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-10-03'),
  ('2025-10-06',   -80.00, 'EDF octobre',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-10-04'),
  ('2025-10-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-10-05'),
  ('2025-10-12',  -390.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2025-10-06'),
  ('2025-10-18',   -90.00, 'Restaurant + soirée amis',       'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-10-07'),
  ('2025-10-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-10-08'),
  ('2025-10-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-10-09'),
  ('2025-10-25',  -400.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-10-10'),
  ('2025-10-30',   -55.00, 'PAIEMENT CB 3010',               'bank',   'personal', NULL,                  'dev:perso:2025-10-11'),

  -- Novembre 2025
  ('2025-11-02',  1800.00, 'Virement Phi Rising nov',        'manual', 'personal', NULL,                  'dev:perso:2025-11-01'),
  ('2025-11-02',  1200.00, 'Virement Booth nov',             'manual', 'personal', NULL,                  'dev:perso:2025-11-02'),
  ('2025-11-05',  -900.00, 'Loyer novembre',                 'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-11-03'),
  ('2025-11-06',   -80.00, 'EDF novembre',                   'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-11-04'),
  ('2025-11-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-11-05'),
  ('2025-11-12',  -410.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2025-11-06'),
  ('2025-11-15',   -72.00, 'Amazon — livres',                'bank',   'personal', 'Achats',              'dev:perso:2025-11-07'),
  ('2025-11-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-11-08'),
  ('2025-11-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-11-09'),
  ('2025-11-25',  -200.00, 'Virement épargne LDDS',          'bank',   'personal', 'Epargne',             'dev:perso:2025-11-10'),

  -- Décembre 2025
  ('2025-12-02',  1500.00, 'Virement Phi Rising déc',        'manual', 'personal', NULL,                  'dev:perso:2025-12-01'),
  ('2025-12-02',  1000.00, 'Virement Booth déc',             'manual', 'personal', NULL,                  'dev:perso:2025-12-02'),
  ('2025-12-05',  -900.00, 'Loyer décembre',                 'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2025-12-03'),
  ('2025-12-06',   -80.00, 'EDF décembre',                   'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2025-12-04'),
  ('2025-12-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2025-12-05'),
  ('2025-12-10',  -430.00, 'Courses Carrefour + Leclerc',    'bank',   'personal', 'Repas',               'dev:perso:2025-12-06'),
  ('2025-12-20',  -120.00, 'Restaurant de Noël en famille',  'bank',   'personal', 'Restau / Soirée',     'dev:perso:2025-12-07'),
  ('2025-12-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-12-08'),
  ('2025-12-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2025-12-09'),
  ('2025-12-25',  -200.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2025-12-10'),
  ('2025-12-27',  -200.00, 'Cadeaux de Noël — FNAC + Amazon','bank',   'personal', 'Achats',              'dev:perso:2025-12-11'),
  ('2025-12-29',   -65.00, 'PRELEVEMENT SERV 2912',          'bank',   'personal', NULL,                  'dev:perso:2025-12-12'),

  -- Janvier 2026
  ('2026-01-02',  1800.00, 'Virement Phi Rising jan',        'manual', 'personal', NULL,                  'dev:perso:2026-01-01'),
  ('2026-01-02',  1000.00, 'Virement Booth jan',             'manual', 'personal', NULL,                  'dev:perso:2026-01-02'),
  ('2026-01-05',  -900.00, 'Loyer janvier',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2026-01-03'),
  ('2026-01-06',   -80.00, 'EDF janvier',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2026-01-04'),
  ('2026-01-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2026-01-05'),
  ('2026-01-12',  -390.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2026-01-06'),
  ('2026-01-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-01-07'),
  ('2026-01-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-01-08'),
  ('2026-01-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2026-01-09'),
  ('2026-01-30',   -72.00, 'Amazon MKTPLACE 3001',           'bank',   'personal', NULL,                  'dev:perso:2026-01-10'),

  -- Février 2026
  ('2026-02-02',  2000.00, 'Virement Phi Rising fév',        'manual', 'personal', NULL,                  'dev:perso:2026-02-01'),
  ('2026-02-02',  1200.00, 'Virement Booth fév',             'manual', 'personal', NULL,                  'dev:perso:2026-02-02'),
  ('2026-02-05',  -900.00, 'Loyer février',                  'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2026-02-03'),
  ('2026-02-06',   -80.00, 'EDF février',                    'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2026-02-04'),
  ('2026-02-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2026-02-05'),
  ('2026-02-12',  -420.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2026-02-06'),
  ('2026-02-14',   -80.00, 'Restaurant Saint-Valentin',      'bank',   'personal', 'Restau / Soirée',     'dev:perso:2026-02-07'),
  ('2026-02-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-02-08'),
  ('2026-02-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-02-09'),
  ('2026-02-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2026-02-10'),

  -- Mars 2026
  ('2026-03-02',  2200.00, 'Virement Phi Rising mar',        'manual', 'personal', NULL,                  'dev:perso:2026-03-01'),
  ('2026-03-02',  1500.00, 'Virement Booth mar',             'manual', 'personal', NULL,                  'dev:perso:2026-03-02'),
  ('2026-03-05',  -900.00, 'Loyer mars',                     'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2026-03-03'),
  ('2026-03-06',   -80.00, 'EDF mars',                       'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2026-03-04'),
  ('2026-03-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2026-03-05'),
  ('2026-03-12',  -400.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2026-03-06'),
  ('2026-03-18',   -80.00, 'Restaurant brasserie',           'bank',   'personal', 'Restau / Soirée',     'dev:perso:2026-03-07'),
  ('2026-03-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-03-08'),
  ('2026-03-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-03-09'),
  ('2026-03-25',  -400.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2026-03-10'),
  ('2026-03-28',   -95.00, 'CB ONLINE ACHAT',                'bank',   'personal', NULL,                  'dev:perso:2026-03-11'),

  -- Avril 2026
  ('2026-04-02',  2000.00, 'Virement Phi Rising avr',        'manual', 'personal', NULL,                  'dev:perso:2026-04-01'),
  ('2026-04-02',  1200.00, 'Virement Booth avr',             'manual', 'personal', NULL,                  'dev:perso:2026-04-02'),
  ('2026-04-05',  -900.00, 'Loyer avril',                    'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2026-04-03'),
  ('2026-04-06',   -80.00, 'EDF avril',                      'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2026-04-04'),
  ('2026-04-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2026-04-05'),
  ('2026-04-12',  -410.00, 'Courses Carrefour',              'bank',   'personal', 'Repas',               'dev:perso:2026-04-06'),
  ('2026-04-20',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-04-07'),
  ('2026-04-20',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-04-08'),
  ('2026-04-25',  -300.00, 'Virement épargne Livret A',      'bank',   'personal', 'Epargne',             'dev:perso:2026-04-09'),
  ('2026-04-28',  -130.00, 'FNAC — livres & jeux',           'bank',   'personal', 'Autre Loisir',        'dev:perso:2026-04-10'),

  -- Mai 2026 (jusqu''au 19 mai)
  ('2026-05-02',  1800.00, 'Virement Phi Rising mai',        'manual', 'personal', NULL,                  'dev:perso:2026-05-01'),
  ('2026-05-02',   900.00, 'Virement Booth mai',             'manual', 'personal', NULL,                  'dev:perso:2026-05-02'),
  ('2026-05-05',  -900.00, 'Loyer mai',                      'bank',   'personal', 'Loyer / Mensualité',  'dev:perso:2026-05-03'),
  ('2026-05-06',   -80.00, 'EDF mai',                        'bank',   'personal', 'Autre Obligatoire',   'dev:perso:2026-05-04'),
  ('2026-05-06',   -45.00, 'Orange internet',                'bank',   'personal', 'Abonnement',          'dev:perso:2026-05-05'),
  ('2026-05-12',  -380.00, 'Courses Leclerc',                'bank',   'personal', 'Repas',               'dev:perso:2026-05-06'),
  ('2026-05-14',   -28.00, 'Pharmacie',                      'bank',   'personal', 'Médical',             'dev:perso:2026-05-07'),
  ('2026-05-15',   -16.00, 'Netflix',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-05-08'),
  ('2026-05-15',   -10.00, 'Spotify',                        'bank',   'personal', 'Abonnement',          'dev:perso:2026-05-09'),
  ('2026-05-17',   -43.00, 'VIRT DIVERS 1705',               'bank',   'personal', NULL,                  'dev:perso:2026-05-10')
ON CONFLICT (external_id) DO NOTHING;
