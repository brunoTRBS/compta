-- Seed 004 : Comptes réels du foyer
-- Exécuter APRÈS la migration 006.
-- Idempotent : peut être relancé sans effet si déjà exécuté (ON CONFLICT / IS NULL).

-- ---------------------------------------------------------------------------
-- 1. Création des 5 comptes réels
-- ---------------------------------------------------------------------------
INSERT INTO accounts (name, institution, type, owner, currency, balance) VALUES
    ('Compte pro coaching',   'Hello Bank', 'current', 'phi_rising',    'EUR', 0),
    ('Compte pro photobooth', 'Revolut',    'revolut', 'booth_in_lyon', 'EUR', 0),
    ('Compte perso',          'Boursobank', 'current', 'personal',      'EUR', 0),
    ('Compte commun',         'Hello Bank', 'current', 'personal',      'EUR', 0),
    ('Livret épargne',        'Boursobank', 'savings', 'personal',      'EUR', 0)
ON CONFLICT (name, owner) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Rattachement par défaut des transactions historiques (best-effort)
-- ---------------------------------------------------------------------------
-- Phi Rising et Booth in Lyon n'ont qu'un seul compte bancaire chacun :
-- rattachement fiable à 100 %.
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

-- Perso couvre 3 comptes réels (Compte perso / Compte commun / Livret) :
-- rattachement par défaut au Compte perso, à corriger au cas par cas depuis
-- Saisie > Corriger des transactions au fil de l'eau.
UPDATE transactions t
SET account_id = a.id
FROM accounts a
WHERE a.name = 'Compte perso' AND a.owner = 'personal'
  AND t.business_id = 'personal' AND t.account_id IS NULL;
