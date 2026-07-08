-- Migration 006 : Rattachement des transactions à un compte réel + transferts
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 005.
--
-- Contexte : jusqu'ici une transaction ne connaît que son business_id
-- (phi_rising / booth_in_lyon / personal), pas le compte bancaire réel sur
-- lequel elle est passée. Impossible donc de distinguer Boursobank perso,
-- le compte commun Hello Bank et le Livret d'épargne (tous rangés sous
-- "personal"), et impossible de noter un virement entre deux comptes.
--
-- Cette migration ajoute :
--   - account_id        : quel compte réel (accounts.id) porte la transaction
--   - is_transfer       : true si c'est un mouvement interne (jamais compté
--                         dans le CA, les dépenses ou l'URSSAF)
--   - transfer_group_id : relie les 2 écritures (sortie + entrée) d'un même
--                         virement
--
-- Une contrainte unique (name, owner) est ajoutée sur accounts pour permettre
-- un seed idempotent des 5 comptes réels (voir infra/seeds/004_real_accounts.sql).

ALTER TABLE accounts
    ADD CONSTRAINT accounts_name_owner_unique UNIQUE (name, owner);

ALTER TABLE transactions
    ADD COLUMN account_id        uuid REFERENCES accounts(id),
    ADD COLUMN is_transfer       boolean NOT NULL DEFAULT false,
    ADD COLUMN transfer_group_id uuid;

CREATE INDEX idx_transactions_account_id     ON transactions (account_id);
CREATE INDEX idx_transactions_transfer_group ON transactions (transfer_group_id)
    WHERE transfer_group_id IS NOT NULL;

-- business_id reste la source de vérité pour le calcul URSSAF (par activité).
-- account_id est la source de vérité pour "dans quel compte est cet argent" —
-- les deux coexistent, aucune des deux ne remplace l'autre.
