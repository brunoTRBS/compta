-- Migration 008 : Import des relevés bancaires multi-comptes
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 007.
--
-- Contexte : les relevés CSV (BoursoBank, Crédit Mutuel) deviennent la source
-- principale des transactions, à la place de la saisie au fil de l'eau.
--
-- Cette migration ajoute :
--   - accounts.bank_account_number : n° de compte tel qu'il apparaît dans le
--     relevé (colonne "Numéro Compte" BoursoBank, nom du fichier Crédit Mutuel).
--     Renseigné depuis la page Sync au premier import d'un compte inconnu, puis
--     utilisé pour reconnaître le compte automatiquement.
--   - transactions.raw_label   : libellé brut de la banque (le champ label
--     reçoit le libellé nettoyé quand la banque en propose un).
--   - transactions.bank_category : catégorie proposée par la banque (BoursoBank),
--     conservée comme suggestion pour la catégorisation.
--
-- Le compte commun est désormais au Crédit Mutuel (et non plus Hello Bank).

ALTER TABLE accounts
    ADD COLUMN bank_account_number text UNIQUE;

ALTER TABLE transactions
    ADD COLUMN raw_label     text,
    ADD COLUMN bank_category text;

UPDATE accounts
SET institution = 'Crédit Mutuel'
WHERE name = 'Compte commun' AND owner = 'personal';
