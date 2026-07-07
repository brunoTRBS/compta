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
DO $$ BEGIN
    CREATE ROLE app_reader WITH LOGIN PASSWORD '<APP_READER_PASSWORD>';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
GRANT CONNECT ON DATABASE postgres TO app_reader;
GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;
-- BYPASSRLS requis : app_reader se connecte directement (pas de JWT), auth.uid() = NULL
-- sans ce privilege, toutes les policies RLS bloquent silencieusement toutes les lignes
ALTER ROLE app_reader BYPASSRLS;

-- ---------------------------------------------------------------------------
-- 2. RLS : remplacer "allow all" par "owner only" sur chaque table
-- ---------------------------------------------------------------------------

-- transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON transactions;
DROP POLICY IF EXISTS "owner_only" ON transactions;
CREATE POLICY "owner_only" ON transactions
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));

-- accounts
DROP POLICY IF EXISTS "allow_all_authenticated" ON accounts;
DROP POLICY IF EXISTS "owner_only" ON accounts;
CREATE POLICY "owner_only" ON accounts
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));

-- account_balance_history
DROP POLICY IF EXISTS "allow_all_authenticated" ON account_balance_history;
DROP POLICY IF EXISTS "owner_only" ON account_balance_history;
CREATE POLICY "owner_only" ON account_balance_history
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));

-- categorization_rules
DROP POLICY IF EXISTS "allow_all_authenticated" ON categorization_rules;
DROP POLICY IF EXISTS "owner_only" ON categorization_rules;
CREATE POLICY "owner_only" ON categorization_rules
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));

-- stripe_transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON stripe_transactions;
DROP POLICY IF EXISTS "owner_only" ON stripe_transactions;
CREATE POLICY "owner_only" ON stripe_transactions
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));

-- categories
DROP POLICY IF EXISTS "allow_all_authenticated" ON categories;
DROP POLICY IF EXISTS "owner_only" ON categories;
CREATE POLICY "owner_only" ON categories
    FOR ALL
    USING  (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid))
    WITH CHECK (auth.uid() IN ('f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid));
