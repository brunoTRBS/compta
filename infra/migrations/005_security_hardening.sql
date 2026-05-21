-- Migration 005 : Durcissement sécurité
-- 1. Rôle PostgreSQL restreint pour connectorx (lecture seule)
-- 2. RLS restrictives par UID propriétaire
--
-- AVANT d'exécuter :
--   a) Remplacer <APP_READER_PASSWORD> par un mot de passe fort
--   b) Remplacer <BRUNO_UID> par l'UUID du compte Supabase Auth
--      (Dashboard → Authentication → Users → copier l'UUID)
--   c) Mettre à jour DB_URL dans secrets.toml :
--      postgresql://app_reader:<APP_READER_PASSWORD>@db.<ref>.supabase.co:5432/postgres

-- ---------------------------------------------------------------------------
-- 1. Rôle lecture seule pour connectorx
-- ---------------------------------------------------------------------------

CREATE ROLE app_reader WITH LOGIN PASSWORD 'lMzKm86RUfJwCLRZ';
GRANT CONNECT ON DATABASE postgres TO app_reader;
GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;

-- ---------------------------------------------------------------------------
-- 2. RLS : remplacer "allow all" par "owner only" sur chaque table
-- ---------------------------------------------------------------------------

-- transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON transactions;
CREATE POLICY "owner_only" ON transactions
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));

-- accounts
DROP POLICY IF EXISTS "allow_all_authenticated" ON accounts;
CREATE POLICY "owner_only" ON accounts
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));

-- account_balance_history
DROP POLICY IF EXISTS "allow_all_authenticated" ON account_balance_history;
CREATE POLICY "owner_only" ON account_balance_history
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));

-- categorization_rules
DROP POLICY IF EXISTS "allow_all_authenticated" ON categorization_rules;
CREATE POLICY "owner_only" ON categorization_rules
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));

-- stripe_transactions
DROP POLICY IF EXISTS "allow_all_authenticated" ON stripe_transactions;
CREATE POLICY "owner_only" ON stripe_transactions
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));

-- categories
DROP POLICY IF EXISTS "allow_all_authenticated" ON categories;
CREATE POLICY "owner_only" ON categories
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));
