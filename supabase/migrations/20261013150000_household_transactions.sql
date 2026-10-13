-- Migration 009 : Opérations du foyer (compte commun)
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 008,
-- et AVANT de déployer le code correspondant (les pages lisent ces colonnes).
--
-- Le compte commun est alimenté chaque mois par une participation qui couvre toutes
-- les dépenses communes. Ses opérations sont donc importées mais exclues du budget
-- perso, sauf les achats perso faits avec la carte de l'utilisatrice.
--
--   - is_household : opération du foyer — enregistrée, mais hors budget perso.
--   - needs_review : à vérifier par l'utilisatrice après import (ses paiements
--                    carte et ses virements reçus sur le compte commun).

ALTER TABLE transactions
    ADD COLUMN is_household boolean NOT NULL DEFAULT false,
    ADD COLUMN needs_review boolean NOT NULL DEFAULT false;

CREATE INDEX idx_transactions_needs_review ON transactions (needs_review)
    WHERE needs_review;
