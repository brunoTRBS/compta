# COMPTA
Gestion Micro-Entreprises & Budget Perso

Application d'aide à la comptabilité et au suivi budgétaire développée sur mesure. Elle permet de piloter plusieurs activités en micro-entreprise distinctes tout en gardant un œil sur la gestion du patrimoine et du budget personnel.

## Objectifs du Projet

L'application répond à deux besoins majeurs :
- Pilotage Business : Suivi de la performance (CA, charges, cotisations URSSAF) pour deux activités de micro-entreprise séparées :
  - "Phi Rising" : activité de coaching (présentiel, distanciel, formation, etc.).
  - "Booth in Lyon" : activité de location de photobooth.
- Pilotage Personnel : Suivi des dépenses par catégories, capacité d'épargne et état des lieux des actifs sur différents comptes bancaires d'un couple.

## Stack Technique
- Frontend : Streamlit
- Processing : Polars
- Database : Supabase
- Automatisation : APIs GoCardless & Stripe

## Spécifications Fonctionnelles
### Gestion Multi-Activité (Business)
- Séparation des flux : Chaque transaction doit être affectée à l'Activité A, l'Activité B ou au Perso.
- Tableau de bord Business : - Calcul du CA encaissé par période.
  - Estimation automatique des cotisations sociales (calculé selon le taux spécifique de chaque activité).
  - Visualisation de la marge réelle après frais et charges.

### Gestion du Budget Personnel
- Catégorisation : Ventilation des dépenses (Loyer, Courses, Loisirs, Epargne, etc.).
- Suivi d'Épargne : Visualisation de l'évolution des soldes sur les différents comptes (Courants, Livrets, Revolut).
- Bilan Patrimonial : État des lieux global de ce que "possède" le foyer à l'instant T.

### Automatisation & Saisie
- Collecte Auto : Importation via API des flux bancaires et Stripe.
- Matching Intelligent : Système de règles pour catégoriser automatiquement les dépenses récurrentes.
- Saisie Manuelle : Possibilité d'ajouter des transactions (espèces) ou d'ajuster des imports via une interface tableur.

### Structure du Repo
- app/ : Fichiers de l'application Streamlit (Pages et Components).
- src/ : Logique métier et transformations Polars.
- tests/ : Suite de tests Pytest.
- infra/ : Scripts SQL pour Supabase.
- .claude/skills/ : Instructions spécialisées pour l'IA.

### Sécurité
Les secrets et clés d'API ne doivent jamais être poussés sur ce dépôt. Utilisez le fichier .streamlit/secrets.toml en local et les "Secrets" sur Streamlit Cloud.