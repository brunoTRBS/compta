-- Migration 012 : Budget du foyer (compte commun)
-- Exécuter dans l'éditeur SQL Supabase (Dashboard > SQL Editor), après la migration 011,
-- et AVANT de déployer le code correspondant.
--
--   - transactions.is_exceptional : opération hors budget courant (apport, caution…),
--     affichée à part pour ne pas fausser les moyennes du foyer.
--   - categorization_rules.is_household : la règle classe les opérations du foyer
--     (catégories du foyer) OU celles du budget perso/pro — jamais les deux, pour
--     qu'une règle « LECLERC → Courses » du foyer ne touche pas les achats perso.
--   - categorization_rules.direction : 'expense' / 'income' / NULL (les deux) — un
--     même nom (ex : un virement de Bruno) peut être une rentrée ou une sortie.
--   - catégories du foyer (business_id = 'household', modifiables dans Paramètres)
--     et premières règles, d'après le relevé du compte commun.

ALTER TABLE transactions
    ADD COLUMN is_exceptional boolean NOT NULL DEFAULT false;

ALTER TABLE categorization_rules
    ADD COLUMN is_household boolean NOT NULL DEFAULT false,
    ADD COLUMN direction    text CHECK (direction IN ('income', 'expense'));

INSERT INTO categories (business_id, name, direction) VALUES
    ('household', 'Courses',              'expense'),
    ('household', 'Prêt immobilier',      'expense'),
    ('household', 'Assurances',           'expense'),
    ('household', 'Énergie & eau',        'expense'),
    ('household', 'Transport',            'expense'),
    ('household', 'Voiture',              'expense'),
    ('household', 'Santé',                'expense'),
    ('household', 'Animaux',              'expense'),
    ('household', 'Maison & équipement',  'expense'),
    ('household', 'Travaux',              'expense'),
    ('household', 'Sorties & restaurants','expense'),
    ('household', 'Frais bancaires',      'expense'),
    ('household', 'Divers',               'expense'),
    ('household', 'Achats perso Bruno',   'expense'),
    ('household', 'Épargne Bruno',        'expense'),
    ('household', 'Participation Charlotte', 'income'),
    ('household', 'Salaire Bruno',        'income'),
    ('household', 'Virements Bruno',      'income'),
    ('household', 'Autres rentrées',      'income')
ON CONFLICT (business_id, name, direction) DO NOTHING;

INSERT INTO categorization_rules (pattern, business_id, category, priority, is_household, direction) VALUES
    ('DATALYO',              'personal', 'Salaire Bruno',           150, true, 'income'),
    ('CHARLOTTE PARIS',      'personal', 'Participation Charlotte', 150, true, 'income'),
    ('TARBES BRUNO',         'personal', 'Virements Bruno',         140, true, 'income'),
    ('BRUNO TARBES',         'personal', 'Virements Bruno',         140, true, 'income'),
    -- Virement mensuel de Bruno vers son épargne (sortie à son nom)
    ('TARBES BRUNO',         'personal', 'Épargne Bruno',           140, true, 'expense'),
    ('BRUNO TARBES',         'personal', 'Épargne Bruno',           140, true, 'expense'),
    ('ECH PRET',             'personal', 'Prêt immobilier',         150, true, 'expense'),
    ('COMMIS PRET',          'personal', 'Prêt immobilier',         150, true, 'expense'),
    ('MATMUT',               'personal', 'Assurances',              150, true, 'expense'),
    ('ASSURANCE HABITATION', 'personal', 'Assurances',              150, true, 'expense'),
    ('SNCF',                 'personal', 'Transport',               150, true, 'expense'),
    ('F COTIS',              'personal', 'Frais bancaires',         150, true, 'expense'),
    ('ADHESION PART SOCIALE','personal', 'Frais bancaires',         150, true, 'expense'),
    ('LECLERC',              'personal', 'Courses',                 150, true, 'expense'),
    ('CARREFOUR',            'personal', 'Courses',                 150, true, 'expense'),
    ('CAREREFOUR',           'personal', 'Courses',                 150, true, 'expense');
