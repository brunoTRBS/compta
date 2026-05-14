# Roadmap — Compta Pro & Perso

Gestion comptable pour deux micro-entreprises (Phi Rising, Booth in Lyon) et budget personnel d'un foyer.

---

## Phase 0 — Fondations (Infrastructure & Architecture)

Objectif : mettre en place la structure de projet propre avant d'écrire la moindre logique métier.

- [x] Créer l'arborescence cible :
  ```
  app/
    pages/
    components/
  src/
    services/       # Supabase, Stripe, GoCardless
    logic/          # Transformations Polars, calculs URSSAF
    utils/          # Dates, devises, formatage
  infra/
    migrations/     # Scripts SQL versionnés
    seeds/          # Données de référence (catégories, taux)
  tests/
    unit/
    integration/
  ```
- [x] Configurer `pyproject.toml` (dépendances, linting ruff, pytest)
- [x] Configurer `pytest` avec fixtures de base (`tests/conftest.py` : mock Supabase, Stripe, GoCardless, DataFrame de transactions)
- [x] Ajouter `.env.example` documentant toutes les variables requises
- [x] Créer `src/config.py` : constantes métier centralisées (taux URSSAF par activité, TVA, plafonds)

---

## Phase 1 — Modèle de données & Schéma Supabase

Objectif : définir le schéma SQL stable qui supporte les deux activités et le perso.

### Tables principales
- [x] `transactions` — table centrale avec enums, index, RLS, colonne `is_income` générée
- [x] `accounts` + `account_balance_history` — comptes et snapshots journaliers
- [x] `categorization_rules` — règles de matching automatique par priorité
- [x] `stripe_transactions` — cache des paiements Stripe avec FK nullable vers transactions

### Migrations
- [x] `infra/migrations/001_init_transactions.sql` — enums + table transactions
- [x] `infra/migrations/002_init_accounts.sql` — accounts + balance_history
- [x] `infra/migrations/003_categorization_rules.sql`
- [x] `infra/migrations/004_stripe_transactions.sql`
- [x] `infra/seeds/001_categories.sql` (règles de catégorisation par défaut)
- [x] `infra/seeds/002_urssaf_rates.sql` (taux 2024 & 2025, table `urssaf_rates`)

### Service layer
- [x] `src/services/supabase.py` — client singleton, CRUD transactions/accounts/rules
- [x] `src/services/db_reader.py` — lectures analytiques via connectorx → Polars, `@st.cache_data`

---

## Phase 2 — Module Business (Phi Rising & Booth in Lyon)

Objectif : tableau de bord opérationnel pour les deux activités de micro-entreprise.

### Logique métier
- [x] `src/logic/urssaf.py` — `UrssafResult`, `compute_cotisations`, `compute_quarterly_estimate`
- [x] `src/logic/revenue.py` — `aggregate_monthly` (12 mois toujours présents), `compute_ytd_summary`, `compute_net_margin`
- [x] `src/logic/categorizer.py` — `apply_rules`, `get_pending_categorization`, `categorization_stats`
- [x] `tests/unit/test_urssaf.py` — 17 tests (CA=0, dépassement seuil, arrondi, versement libératoire…)
- [x] `tests/unit/test_revenue.py` — 14 tests
- [x] `tests/unit/test_categorizer.py` — 13 tests (case-insensitive, scoping business, stats…)
- [x] **48/48 tests passent**

### Pages Streamlit
- [x] `app/main.py` — entrypoint multi-page (`streamlit run app/main.py`)
- [x] `app/components/transaction_table.py` — `st.data_editor` Polars natif, SelectboxColumn catégories, callback save
- [x] `app/components/business_dashboard.py` — dashboard partagé (KPIs, graphiques bar/horizontal, table éditable)
- [x] `app/pages/1_Phi_Rising.py` — appelle `render_dashboard(BusinessId.PHI_RISING, …)`
- [x] `app/pages/2_Booth_in_Lyon.py` — appelle `render_dashboard(BusinessId.BOOTH_IN_LYON, …)`

---

## Phase 3 — Module Budget Personnel

Objectif : suivi des dépenses, de l'épargne et du patrimoine du foyer.

### Logique métier
- [x] `src/logic/budget.py` — `breakdown_by_category` (pct inclus), `compute_savings_rate`, `compute_budget_summary`
- [x] `src/logic/patrimoine.py` — `aggregate_by_account_type`, `compute_net_worth`, `compute_patrimoine_evolution`, `group_by_owner`
- [x] `tests/unit/test_budget.py` — 23 tests
- [x] `tests/unit/test_patrimoine.py` — 18 tests
- [x] **89/89 tests passent**

### Pages Streamlit
- [x] `app/pages/3_Budget_Perso.py` — KPIs (revenus/dépenses/épargne/taux), bar chart catégories, line chart mensuel, catégorisation auto + manuelle
- [x] `app/pages/4_Patrimoine.py` — KPIs par owner, pie chart par type, tableau comptes, line chart évolution, `st.form` mise à jour solde
- [x] `src/services/db_reader.py` — ajout `read_patrimoine_evolution` (JOIN accounts + history)

---

## Phase 4 — Automatisation & Collecte

Objectif : brancher les APIs pour réduire la saisie manuelle à zéro.

### GoCardless (flux bancaires)
- [x] `src/services/gocardless.py` — auth avec cache session, `list_accounts`, `fetch_transactions` (booked), `map_transaction`
- [x] `tests/integration/test_gocardless.py` — 13 tests (mapping pur + HTTP mocké + cache token)

### Stripe (paiements pro)
- [x] `src/services/stripe_client.py` — `fetch_payment_intents` (filtre metadata), `fetch_refunds`, `map_payment_intent`, `map_stripe_cache_row`
- [x] `tests/integration/test_stripe.py` — 14 tests (mapping pur + API mockée)

### Pipeline d'import
- [x] `src/logic/import_pipeline.py` — `ImportReport`, `deduplicate`, `categorize`, `run_full_pipeline`
- [x] `tests/unit/test_import_pipeline.py` — 19 tests (dédup, catégorisation, erreur DB, skip si tout doublon)
- [x] `app/pages/5_Sync.py` — `st.status()` pour GoCardless et Stripe, rapport d'import en métriques
- [x] `tests/conftest.py` — stubs streamlit/supabase/stripe pour tests sans dépendances lourdes
- [x] **135/135 tests passent**

---

## Phase 5 — Saisie Manuelle & Corrections

Objectif : permettre d'ajouter des espèces et corriger les catégorisations automatiques.

- [x] `app/pages/5_Saisie.py` — 3 onglets : st.form saisie manuelle · file catégorisation + auto · correction complète (diff + update + delete)
- [x] `src/services/supabase.py` — `upsert_transaction`, `update_transaction` (filtre champs immutables), `delete_transaction`
- [x] `tests/unit/test_supabase_service.py` — 10 tests (upsert, update strip immutables, delete, bulk_update_categories)
- [x] `app/pages/5_Sync.py` renommé en `6_Sync.py` (ordre de navigation cohérent)
- [x] **145/145 tests passent**

---

## Phase 6 — Qualité & Mise en Production

Objectif : fiabiliser et déployer sur Streamlit Cloud.

- [x] Suite de tests complète — **159/159 tests, 98 % de couverture sur `src/logic/`** (cible : 80 %)
  - `tests/unit/` : urssaf, revenue, categorizer, budget, patrimoine, import_pipeline, supabase_service
  - `tests/integration/` : gocardless, stripe, db_reader (requêtes SQL mockées)
- [x] CI GitHub Actions — `.github/workflows/ci.yml` : lint ruff + tests unit + tests integration + coverage gate ≥ 80 %
- [x] Configuration Streamlit Cloud — `requirements.txt` avec contraintes de version · `pyproject.toml` avec `pytest-cov`
- [x] `app/pages/7_Settings.py` — statut Supabase/Stripe/GoCardless avec latence · cache flush · template secrets.toml
- [x] `src/utils/health.py` — `check_supabase`, `check_stripe`, `check_gocardless`, `run_all_checks`
- [x] `app/main.py` — navigation mise à jour (7 pages)

---

## Backlog (post-MVP)

- Export CSV/Excel des transactions par période et par activité
- Notifications email (résumé mensuel URSSAF à payer)
- Gestion multi-devises (Revolut en GBP/USD → conversion EUR)
- Dashboard de comparaison N vs N-1 (Polars join sur années)
- Règles de catégorisation via interface (CRUD sur `categorization_rules`)
- Import CSV bancaire manuel (Crédit Mutuel, CIC…) en fallback GoCardless
