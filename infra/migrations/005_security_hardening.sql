-- Migration 005 : Durcissement sécurité
-- 1. Rôle PostgreSQL restreint pour connectorx (lecture seule)
-- 2. RLS restrictives par UID propriétaire
--
-- AVANT d'exécuter :
--   a) Remplacer <APP_READER_PASSWORD> par un mot de passe fort
--   b) Mettre à jour les UUID (Dashboard → Authentication → Users → copier l'UUID)
--   c) Mettre à jour DB_URL dans secrets.toml :
--      postgresql://app_reader:<APP_READER_PASSWORD>@db.<ref>.supabase.co:5432/postgres

-- ---------------------------------------------------------------------------
-- 1. Rôle lecture seule pour connectorx
-- ---------------------------------------------------------------------------

-- NE PAS VERSIONNER le vrai mot de passe ici.
-- Exécuter la rotation directement : supabase db query --linked "ALTER ROLE app_reader WITH PASSWORD '<votre_mot_de_passe>';"
CREATE ROLE app_reader WITH LOGIN PASSWORD '<APP_READER_PASSWORD>';
GRANT CONNECT ON DATABASE postgres TO app_reader;
GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;

-- ---------------------------------------------------------------------------
-- 2. RLS : remplacer "allow all" par "owner only" sur chaque table
-- ---------------------------------------------------------------------------

-- transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON transactions;
DROP POLICY IF EXISTS "owner_only" ON transactions;
CREATE POLICY "owner_only" ON transactions
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));

-- accounts
DROP POLICY IF EXISTS "allow_all_authenticated" ON accounts;
DROP POLICY IF EXISTS "owner_only" ON accounts;
CREATE POLICY "owner_only" ON accounts
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));

-- account_balance_history
DROP POLICY IF EXISTS "allow_all_authenticated" ON account_balance_history;
DROP POLICY IF EXISTS "owner_only" ON account_balance_history;
CREATE POLICY "owner_only" ON account_balance_history
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));

-- categorization_rules
DROP POLICY IF EXISTS "allow_all_authenticated" ON categorization_rules;
DROP POLICY IF EXISTS "owner_only" ON categorization_rules;
CREATE POLICY "owner_only" ON categorization_rules
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));

-- stripe_transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON stripe_transactions;
DROP POLICY IF EXISTS "owner_only" ON stripe_transactions;
CREATE POLICY "owner_only" ON stripe_transactions
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));

-- categories
DROP POLICY IF EXISTS "allow_all_authenticated" ON categories;
DROP POLICY IF EXISTS "owner_only" ON categories;
CREATE POLICY "owner_only" ON categories
    FOR ALL
    USING  (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid))
    WITH CHECK (auth.uid() IN ('9a18d6c6-96a8-4ace-8e00-a88e99b0e855'::uuid, '3108ddd3-a23e-494e-8b24-46663ee1cccd'::uuid));
