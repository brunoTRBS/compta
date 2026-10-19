-- Migration 013a : le foyer devient une activité à part entière (étape 1/2)
-- Exécuter SEULE dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la 012.
-- Puis exécuter la 013b dans une exécution SÉPARÉE : PostgreSQL interdit d'utiliser
-- une nouvelle valeur d'énumération dans la même exécution que celle qui l'ajoute.
--
-- AVANT : exporter la table transactions (Table Editor > transactions > Export CSV).
-- La base gratuite n'a pas de sauvegarde automatique.
--
-- Contexte : jusqu'ici le compte commun était rangé sous l'activité « personal » avec
-- un indicateur is_household. L'activité « household » remplace cet indicateur : une
-- opération a une seule affectation (Perso, Foyer, Phi Rising, Booth in Lyon).

ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'household';
