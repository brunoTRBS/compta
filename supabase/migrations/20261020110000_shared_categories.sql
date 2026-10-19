-- Migration 014 : Liste de catégories commune (Perso, Foyer, activités pro)
-- Exécuter dans l'éditeur SQL Supabase APRÈS les migrations 013a et 013b, et AVANT de
-- déployer le code correspondant (les pages lisent la nouvelle colonne group_name).
--
-- Cette migration :
--   1. ajoute categories.group_name (groupe : Logement, Alimentation…) ;
--   2. aligne les catégories du foyer créées par la migration 012 sur la liste commune
--      (opérations et règles comprises) ;
--   3. ajoute la liste commune aux budgets Perso et Foyer ;
--   4. range chaque catégorie dans son groupe.
-- Les anciennes catégories perso (Médical, Repas…) ne sont PAS renommées ici : c'est
-- l'écran Paramètres > Catégories > Remise en ordre qui le fait, avec le nombre
-- d'opérations concernées. Idempotente : peut être relancée sans effet.

ALTER TABLE categories ADD COLUMN IF NOT EXISTS group_name text;

-- ---------------------------------------------------------------------------
-- 2. Foyer : renommages issus de la migration 012
--    Sorties & restaurants -> Restaurants & bars ; Frais bancaires -> Frais bancaires & impôts ;
--    Assurances -> Assurance habitation (le prélèvement Matmut était la dernière assurance
--    habitation de l'ancien logement). Les assurances suivent leur objet : habitation dans
--    Logement, auto dans Voiture, santé dans Santé.
-- ---------------------------------------------------------------------------
UPDATE transactions SET category = 'Restaurants & bars'
    WHERE business_id = 'household' AND category = 'Sorties & restaurants';
UPDATE categorization_rules SET category = 'Restaurants & bars'
    WHERE business_id = 'household' AND category = 'Sorties & restaurants';

UPDATE transactions SET category = 'Frais bancaires & impôts'
    WHERE business_id = 'household' AND category = 'Frais bancaires';
UPDATE categorization_rules SET category = 'Frais bancaires & impôts'
    WHERE business_id = 'household' AND category = 'Frais bancaires';

UPDATE transactions SET category = 'Assurance habitation'
    WHERE business_id = 'household' AND category = 'Assurances';
UPDATE categorization_rules SET category = 'Assurance habitation'
    WHERE business_id = 'household' AND category = 'Assurances';

DELETE FROM categories
    WHERE business_id = 'household'
      AND name IN ('Sorties & restaurants', 'Frais bancaires', 'Assurances');

-- ---------------------------------------------------------------------------
-- 3. Liste commune
-- ---------------------------------------------------------------------------
INSERT INTO categories (business_id, name, direction) VALUES
    -- Perso et Foyer
    ('personal',  'Courses',                  'expense'), ('household', 'Courses',                  'expense'),
    ('personal',  'Restaurants & bars',       'expense'), ('household', 'Restaurants & bars',       'expense'),
    ('personal',  'Transport',                'expense'), ('household', 'Transport',                'expense'),
    ('personal',  'Voiture',                  'expense'), ('household', 'Voiture',                  'expense'),
    ('personal',  'Sorties & loisirs',        'expense'), ('household', 'Sorties & loisirs',        'expense'),
    ('personal',  'Voyages',                  'expense'), ('household', 'Voyages',                  'expense'),
    ('personal',  'Achats',                   'expense'), ('household', 'Achats',                   'expense'),
    ('personal',  'Santé',                    'expense'), ('household', 'Santé',                    'expense'),
    ('personal',  'Abonnements',              'expense'), ('household', 'Abonnements',              'expense'),
    ('personal',  'Animaux',                  'expense'), ('household', 'Animaux',                  'expense'),
    ('personal',  'Frais bancaires & impôts', 'expense'), ('household', 'Frais bancaires & impôts', 'expense'),
    ('personal',  'Divers',                   'expense'), ('household', 'Divers',                   'expense'),
    ('personal',  'Énergie & eau',            'expense'), ('household', 'Énergie & eau',            'expense'),
    ('personal',  'Maison & équipement',      'expense'), ('household', 'Maison & équipement',      'expense'),
    ('personal',  'Travaux',                  'expense'), ('household', 'Travaux',                  'expense'),
    ('personal',  'Assurance habitation',     'expense'), ('household', 'Assurance habitation',     'expense'),
    -- Perso seulement
    ('personal',  'Loyer',                    'expense'),
    ('personal',  'Repas du midi',            'expense'),
    ('personal',  'Épargne',                  'expense'),
    -- Foyer seulement
    ('household', 'Prêt immobilier',          'expense'),
    ('household', 'Achats perso Bruno',       'expense'),
    ('household', 'Épargne Bruno',            'expense'),
    ('household', 'Participation Charlotte',  'income'),
    ('household', 'Salaire Bruno',            'income'),
    ('household', 'Virements Bruno',          'income'),
    ('household', 'Autres rentrées',          'income')
ON CONFLICT (business_id, name, direction) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 4. Groupes (par nom ET sens : « Médical » dépense et « Médical » revenu diffèrent)
-- ---------------------------------------------------------------------------
UPDATE categories AS c
SET group_name = g.group_name
FROM (VALUES
    ('Loyer',                    'expense', 'Logement'),
    ('Prêt immobilier',          'expense', 'Logement'),
    ('Assurance habitation',     'expense', 'Logement'),
    ('Énergie & eau',            'expense', 'Logement'),
    ('Maison & équipement',      'expense', 'Logement'),
    ('Travaux',                  'expense', 'Logement'),
    ('Courses',                  'expense', 'Alimentation'),
    ('Repas du midi',            'expense', 'Alimentation'),
    ('Repas',                    'expense', 'Alimentation'),
    ('Restaurants & bars',       'expense', 'Alimentation'),
    ('Restau / Soirées',         'expense', 'Alimentation'),
    ('Transport',                'expense', 'Transport'),
    ('Voiture',                  'expense', 'Transport'),
    ('Sorties & loisirs',        'expense', 'Loisirs'),
    ('Autres Loisirs',           'expense', 'Loisirs'),
    ('Voyages',                  'expense', 'Loisirs'),
    ('Voyage',                   'expense', 'Loisirs'),
    ('Achats',                   'expense', 'Loisirs'),
    ('Santé',                    'expense', 'Santé'),
    ('Médical',                  'expense', 'Santé'),
    ('Abonnements',              'expense', 'Vie courante'),
    ('Abonnement',               'expense', 'Vie courante'),
    ('Animaux',                  'expense', 'Vie courante'),
    ('Frais bancaires & impôts', 'expense', 'Vie courante'),
    ('Divers',                   'expense', 'Vie courante'),
    ('Autres Obligatoire',       'expense', 'Vie courante'),
    ('Épargne',                  'expense', 'Épargne'),
    ('Epargne',                  'expense', 'Épargne'),
    ('Achats perso Bruno',       'expense', 'Hors dépenses communes'),
    ('Épargne Bruno',            'expense', 'Hors dépenses communes'),
    ('Formations / Autres',      'expense', 'Activité pro'),
    ('Marketing',                'expense', 'Activité pro'),
    ('Prestataires',             'expense', 'Activité pro'),
    ('Stripe',                   'expense', 'Activité pro'),
    ('Consommable',              'expense', 'Activité pro'),
    ('Déplacement',              'expense', 'Activité pro'),
    ('Matériel',                 'expense', 'Activité pro'),
    ('Pub',                      'expense', 'Activité pro'),
    ('Participation Charlotte',  'income',  'Revenus'),
    ('Salaire Bruno',            'income',  'Revenus'),
    ('Virements Bruno',          'income',  'Revenus'),
    ('Autres rentrées',          'income',  'Revenus'),
    ('Autres',                   'income',  'Revenus'),
    ('CAF',                      'income',  'Revenus'),
    ('Médical',                  'income',  'Revenus'),
    ('Photobooth',               'income',  'Revenus'),
    ('BIC',                      'income',  'Revenus'),
    ('BNC',                      'income',  'Revenus'),
    ('ND',                       'income',  'Revenus'),
    ('Évenement Privé',          'income',  'Revenus')
) AS g(name, direction, group_name)
WHERE c.name = g.name AND c.direction = g.direction;
