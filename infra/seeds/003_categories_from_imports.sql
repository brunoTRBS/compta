-- Seed 003 : Catégories issues des imports Google Sheets
-- Réinitialise et réinsère les catégories pour les 3 entités.
-- Exécuter dans le SQL Editor Supabase avant de lancer scripts/load_imports.py

DELETE FROM categories
WHERE business_id IN ('phi_rising', 'booth_in_lyon', 'personal');

INSERT INTO categories (business_id, name, direction) VALUES
-- phi_rising — dépenses
('phi_rising', 'Abonnements',        'expense'),
('phi_rising', 'Formations / Autres','expense'),
('phi_rising', 'Marketing',          'expense'),
('phi_rising', 'Prestataires',       'expense'),
-- phi_rising — revenus
('phi_rising', 'BIC', 'income'),
('phi_rising', 'BNC', 'income'),
('phi_rising', 'ND',  'income'),
-- phi_rising — frais Stripe (négatifs, déductibles du CA avant URSSAF)
('phi_rising', 'Stripe', 'expense'),
-- personal — dépenses
('personal', 'Abonnements',       'expense'),
('personal', 'Achats',            'expense'),
('personal', 'Autres Loisirs',    'expense'),
('personal', 'Autres Obligatoire','expense'),
('personal', 'Epargne',           'expense'),
('personal', 'Loyer',             'expense'),
('personal', 'Médical',           'expense'),
('personal', 'Repas',             'expense'),
('personal', 'Restau / Soirées',  'expense'),
('personal', 'Voyage',            'expense'),
-- personal — revenus
('personal', 'Autres',      'income'),
('personal', 'CAF',         'income'),
('personal', 'Médical',     'income'),
('personal', 'Photobooth',  'income'),
-- booth_in_lyon — dépenses
('booth_in_lyon', 'Abonnement',  'expense'),
('booth_in_lyon', 'Consommable', 'expense'),
('booth_in_lyon', 'Déplacement', 'expense'),
('booth_in_lyon', 'Matériel',    'expense'),
('booth_in_lyon', 'Pub',         'expense'),
-- booth_in_lyon — revenus
('booth_in_lyon', 'ND',             'income'),
('booth_in_lyon', 'Évenement Privé','income');
