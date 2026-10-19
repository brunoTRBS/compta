-- Migration 015 : une règle peut changer l'affectation d'une opération
-- Exécuter dans l'éditeur SQL Supabase APRÈS la 014, et AVANT de déployer le code
-- correspondant (la page À traiter enregistre ce champ à la création d'une règle).
--
-- Jusqu'ici une règle ne donnait qu'une catégorie. Avec target_business_id, elle peut
-- aussi ranger l'opération dans un autre budget : par exemple « DELIVEROO » sur la
-- carte du compte commun -> Perso. Sans cette valeur, l'opération reste dans son budget.
-- (La colonne business_id de la règle garde son sens : le budget des opérations visées.)

ALTER TABLE categorization_rules
    ADD COLUMN IF NOT EXISTS target_business_id business_type;
