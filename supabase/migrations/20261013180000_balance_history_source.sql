-- Migration 011 : Origine des soldes enregistrés (contrôle de solde)
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 010,
-- et AVANT de déployer le code correspondant.
--
-- Chaque relevé importé enregistre le solde réel du compte à sa dernière date. Le
-- contrôle de solde ne compare que ces soldes-là (source = 'statement') : un solde
-- saisi à la main dans Patrimoine, souvent antérieur aux imports, fausserait la
-- comparaison avec les opérations de l'app.

ALTER TABLE account_balance_history
    ADD COLUMN source text NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'statement'));
