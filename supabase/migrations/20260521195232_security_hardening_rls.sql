-- Migration 007 : Durcissement RLS — owner only par UID Supabase Auth
-- Remplace les policies "allow_all_authenticated" (USING true) par des policies
-- restreintes aux UIDs autorisés.

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

-- categories (créée par migration 006)
DROP POLICY IF EXISTS "allow_all_authenticated" ON categories;
CREATE POLICY "owner_only" ON categories
    FOR ALL
    USING  (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid))
    WITH CHECK (auth.uid() IN ('cbe9945c-b7f6-4424-af97-6f81b0e73eb6'::uuid, 'd08b68fd-efde-43f4-85b2-65d0cf4fe5d8'::uuid));
