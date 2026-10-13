-- Migration 010 (ponctuelle, données uniquement) : virements déjà importés à vérifier
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor). Facultative : aucune
-- colonne n'est ajoutée, l'app fonctionne sans.
--
-- Les relevés importés avant la détection des virements (13/10/2026) ont pu faire
-- entrer des virements entre comptes comme de simples dépenses/revenus. Cette requête
-- les signale dans « Virements à vérifier » (page Sync), avec les mêmes critères que
-- src/logic/transfers.py::is_transfer_like.

UPDATE transactions
SET needs_review = true
WHERE source = 'bank'
  AND NOT is_transfer
  AND NOT is_household
  AND NOT needs_review
  AND created_at >= '2026-10-13'
  AND upper(coalesce(raw_label, label)) ~ '\m(VIR|VIREMENT)\M'
  AND upper(coalesce(raw_label, label)) ~ '(CHARLOTTE PARIS|PARIS CHARLOTTE|LIVRET|EPARGNE|ÉPARGNE)';
