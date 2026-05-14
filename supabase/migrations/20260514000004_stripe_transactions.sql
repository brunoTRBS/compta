-- Migration 004 : Cache des paiements Stripe
-- Stocke les PaymentIntents bruts pour éviter les appels API répétés.
-- Liés à transactions via transaction_id une fois réconciliés.

CREATE TABLE stripe_transactions (
    stripe_id       text PRIMARY KEY,       -- PaymentIntent ID (pi_xxx)
    transaction_id  uuid REFERENCES transactions(id) ON DELETE SET NULL,
    business_id     business_type NOT NULL,
    amount          numeric(12, 2) NOT NULL, -- En devise source (avant conversion)
    currency        char(3) NOT NULL DEFAULT 'eur',
    status          text NOT NULL,           -- succeeded | requires_payment_method | refunded…
    customer_email  text,
    description     text,
    metadata        jsonb NOT NULL DEFAULT '{}',
    stripe_created_at timestamptz NOT NULL,
    synced_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_stripe_business_id    ON stripe_transactions (business_id);
CREATE INDEX idx_stripe_status         ON stripe_transactions (status);
CREATE INDEX idx_stripe_created_at     ON stripe_transactions (stripe_created_at DESC);
CREATE INDEX idx_stripe_transaction_id ON stripe_transactions (transaction_id) WHERE transaction_id IS NOT NULL;

ALTER TABLE stripe_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authenticated" ON stripe_transactions
    FOR ALL USING (true) WITH CHECK (true);
