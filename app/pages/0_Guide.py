"""Page Guide — le tutoriel complet : comment se servir de l'app, page par page, avec des exemples."""

import streamlit as st

from app.components.auth import require_auth

st.set_page_config(page_title="Guide", page_icon="📘", layout="wide")
require_auth()
st.title("📘 Guide de l'application")
st.caption(
    "Comment se servir de l'app, page par page, avec des exemples et des scénarios. "
    "Chaque page a aussi sa bulle ℹ️ en haut à droite : elle rappelle l'essentiel de la page ou de l'onglet."
)


def _page(title: str, role: str, sees: list[str], does: list[str], example: str) -> None:
    """Une page de l'app : à quoi elle sert, ce qu'on y voit, ce qu'on y fait, un exemple."""
    with st.expander(title):
        st.markdown(f"**À quoi ça sert** — {role}")
        col_sees, col_does = st.columns(2)
        with col_sees:
            st.markdown("**Ce que tu y vois**\n\n" + "\n".join(f"- {line}" for line in sees))
        with col_does:
            st.markdown("**Ce que tu y fais**\n\n" + "\n".join(f"- {line}" for line in does))
        st.info(f"**Exemple** — {example}")


def _scenario(title: str, situation: str, steps: list[str], result: str) -> None:
    """Un cas concret : la situation, les gestes, ce que l'app en fait."""
    with st.expander(title):
        st.markdown(f"**La situation** — {situation}")
        st.markdown("**Ce que tu fais**\n\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)))
        st.success(f"**Résultat** — {result}")


tab_start, tab_routine, tab_pages, tab_scenarios, tab_lexicon, tab_help = st.tabs([
    "🚀 Démarrer", "📅 Ma routine", "🧭 Page par page", "🎬 Scénarios", "📖 Lexique", "🛟 Dépannage & limites",
])

# ===========================================================================
# DÉMARRER
# ===========================================================================
with tab_start:
    st.header("Le principe")
    st.markdown(
        """
Tu n'as plus à noter tes dépenses. **Chaque semaine** :

1. tu télécharges les relevés de tes banques (fichiers **CSV**) ;
2. tu les déposes sur la page **🔄 Sync** ;
3. tu ouvres **📥 À traiter**, tu corriges ce qui est faux et tu cliques sur **Enregistrer**.

L'app range toute seule ce qu'elle reconnaît. À chaque fois que tu lui apprends quelque chose
(case **Règle**), elle le refait seule la fois suivante : ton travail diminue de semaine en semaine.
"""
    )

    st.header("Le circuit")
    st.code(
        """
 Relevés CSV            🔄 Sync                 📥 À traiter                   Budgets
 (BoursoBank,     ─►   importe, évite     ─►   tu choisis l'affectation  ─►   👤 Perso      🏠 Foyer
  Crédit Mutuel)        les doublons            et la catégorie, puis          💼 Phi Rising  📸 Booth
                                                « Enregistrer »                      │
                                                      ▲                              ▼
                                               🧭 Règles (l'app apprend)     🧮 Vue consolidée · 🏦 Patrimoine

 Pour corriger après coup : 🔎 Transactions     Pour les catégories et la sauvegarde : ⚙️ Paramètres
""",
        language=None,
    )

    st.header("Tes comptes et leur budget")
    st.markdown(
        """
| Compte | Banque | Budget | Comment il arrive dans l'app |
|---|---|---|---|
| Compte perso | BoursoBank | 👤 **Perso** | relevé CSV |
| Compte commun | Crédit Mutuel | 🏠 **Foyer** | relevé CSV |
| Livret épargne | BoursoBank | 👤 Perso (épargne) | relevé CSV, ou solde saisi à la main |
| Compte pro coaching | Hello Bank | 💼 **Phi Rising** | saisie manuelle, récurrences, synchro Stripe |
| Compte pro photobooth | Revolut | 📸 **Booth in Lyon** | saisie manuelle, récurrences, synchro Stripe |
"""
    )

    st.header("Les quatre budgets")
    st.markdown(
        """
- 👤 **Perso** : **ton** argent. Tes revenus comptent le **bénéfice de Phi Rising**, les virements reçus de
  Booth in Lyon et les retraits du Livret. Ta **participation** au foyer y est une dépense (« Loyer »).
- 🏠 **Foyer** : le compte commun. Ce que Bruno et toi y mettez, et tout ce qui en sort (prêt, courses,
  assurances…). Les achats perso de Bruno et son épargne sont isolés.
- 💼 **Phi Rising** et 📸 **Booth in Lyon** : tes deux activités, avec chiffre d'affaires, URSSAF, dépenses et bénéfice.

Chaque opération appartient à **un seul budget** : c'est son **affectation**. Le compte donne une
affectation par défaut (Bourso → Perso, commun → Foyer), que tu peux changer ligne par ligne : un achat perso
payé avec la carte du commun va en Perso.
"""
    )

    st.header("Première utilisation, pas à pas")
    st.markdown(
        """
1. **🔄 Sync** → dépose le CSV de **BoursoBank**. La première fois, l'app demande à quel compte il correspond :
   choisis *Compte perso (Boursobank)*. Elle s'en souviendra. Clique sur **Importer**.
2. Même chose avec le CSV du **Crédit Mutuel** (garde le nom de fichier d'origine : c'est le numéro du compte) →
   *Compte commun (Crédit Mutuel)*.
3. **📥 À traiter** → passe les lignes en revue (voir les scénarios), puis **Enregistrer**.
4. **⚙️ Paramètres → Catégories → Remise en ordre** → aligne tes anciennes catégories sur la liste commune.
5. **💰 Budget Perso → Vue mensuelle** et **🏠 Budget Foyer** : tes chiffres du mois.
"""
    )

# ===========================================================================
# ROUTINE
# ===========================================================================
with tab_routine:
    st.header("Chaque semaine — 10 à 15 minutes")
    st.markdown(
        """
| # | Où | Ce que tu fais |
|---|---|---|
| 1 | Sites des banques | Télécharge le CSV de **BoursoBank** et celui du **Crédit Mutuel** (la période depuis le dernier import suffit : les doublons sont ignorés). |
| 2 | 🔄 **Sync** | Dépose les deux fichiers, vérifie l'aperçu (nouvelles opérations), clique sur **Importer**. |
| 3 | 📥 **À traiter** | Regarde les lignes : corrige l'**affectation** ou la **catégorie** de celles qui sont fausses. Coche **Règle** pour un commerçant habituel. Clique sur **✅ Enregistrer**. |
| 4 | 📥 **À traiter** (bas de page) | Vérifie le **✅ Contrôle des comptes** : chaque compte doit être complet. |
| 5 | 💰 / 🏠 | Un coup d'œil à **Budget Perso** et **Budget Foyer** : où part l'argent ce mois-ci ? |
"""
    )
    st.header("Chaque mois — côté pro")
    st.markdown(
        """
- **💼 Phi Rising** et **📸 Booth in Lyon** → onglet **Récurrences** → *À valider ce mois-ci* : valide tes modèles (abonnements, charges).
- **🔄 Sync → Stripe** : synchronise les paiements du mois pour chaque activité.
- **Vue mensuelle** : contrôle le CA, l'URSSAF estimée et le bénéfice.
- Ta **participation** au foyer et ton virement vers BoursoBank ne se saisissent pas à la main : ils arrivent par les relevés.
"""
    )
    st.header("Exemple : un dimanche soir")
    st.info(
        """
**20 h 00** — tu télécharges les deux CSV. **20 h 03** — tu les déposes sur Sync : *31 opérations lues, 18 déjà importées,
13 nouvelles*. **20 h 04** — **Importer**. **20 h 05** — À traiter : 13 lignes, dont 4 à vérifier (ta carte sur le commun).
Tu passes 2 achats en **Perso**, tu ranges « Boulangerie » en Courses avec **Règle** cochée, tu cliques **Enregistrer**.
**20 h 10** — contrôle des comptes ✅. Terminé.
"""
    )

# ===========================================================================
# PAGE PAR PAGE
# ===========================================================================
with tab_pages:
    st.markdown("Déplie une page pour voir à quoi elle sert, ce que tu y vois, ce que tu y fais, et un exemple.")

    _page(
        "🔄 Sync — importer tes relevés",
        "Importer les relevés bancaires (CSV) et les paiements Stripe. Les opérations déjà importées ou déjà saisies à la main ne sont jamais recréées.",
        [
            "une zone pour déposer un ou plusieurs CSV",
            "pour chaque compte : opérations lues, déjà importées, déjà saisies à la main, nouvelles",
            "la liste des nouvelles opérations avec ce qu'elles deviendront (🏠 Foyer · 🔎 À vérifier · 🔁 Virement interne · 💰 Budget)",
            "un bandeau « N opérations à traiter » après l'import",
            "plus bas, la synchro Stripe",
        ],
        [
            "dépose les CSV ; au 1er import d'un compte, choisis son nom (il est retenu ensuite)",
            "vérifie l'aperçu, puis clique sur **Importer**",
            "Stripe : choisis l'activité et la date de départ, puis **Synchroniser**",
        ],
        "Tu déposes un relevé Bourso déjà importé à moitié : l'aperçu annonce « 20 déjà importées, 6 nouvelles ». Seules les 6 sont enregistrées.",
    )
    _page(
        "📥 À traiter — la boîte de réception",
        "Valider en un endroit tout ce que l'import n'a pas pu décider seul.",
        [
            "des blocs par affectation : 🔁 Virement interne, 🏠 Foyer, 👤 Perso, 💼 Phi Rising, 📸 Booth",
            "une colonne **Type** qui dit pourquoi la ligne est là : 💳 ta carte sur le commun · ↘️ ta participation · 🔁 virement entre tes comptes · 🏷️ à classer",
            "✨ une catégorie suggérée d'après tes choix passés",
            "en bas : le ✅ Contrôle des comptes et un menu 🛠️ Outils",
        ],
        [
            "change l'**Affectation** d'une ligne si le budget est faux",
            "choisis la **Catégorie** ; pour un virement, l'**Autre compte**",
            "coche **Règle** (et vérifie le **Motif**) pour ranger les prochaines seules",
            "clique sur **✅ Enregistrer** : les lignes à vérifier laissées telles quelles sont validées",
        ],
        "Une ligne « PAIEMENT CB LYON DELIVEROO CARTE 3935 » arrive en 🏠 Foyer, 💳. Tu passes l'Affectation sur **Perso**, la catégorie sur *Restaurants & bars*, tu coches **Règle**. La prochaine fois, elle ira directement en Perso.",
    )
    _page(
        "💰 Budget Perso",
        "Suivre ton argent : revenus, dépenses, épargne, reste du mois.",
        [
            "5 onglets : Transactions · Récurrences · Virement · Vue mensuelle · Vue globale",
            "**Vue mensuelle** : Revenus, Dépenses, Épargne, Différence, Reste du mois précédent, Total fin du mois",
            "**Où part l'argent** : barres par groupe, détail par catégorie, variation sur le mois précédent",
            "**Vue globale** : catégories × mois sur une période, courbe revenus / dépenses",
        ],
        [
            "corrige ou ajoute une opération à la main (espèces) dans **Transactions**",
            "choisis l'année et le mois en haut de la Vue mensuelle",
            "active **Ajouter les dépenses communes du foyer** pour la vue d'ensemble (ta participation n'est comptée qu'une fois)",
        ],
        "En octobre : Revenus 3 120 €, Dépenses 1 480 €, Épargne 300 € → Différence 1 340 €. Tu vois que « Alimentation » monte de 12 % : tu ouvres le groupe pour voir quelle catégorie.",
    )
    _page(
        "🏠 Budget Foyer",
        "Suivre le compte commun : ce que vous y mettez, ce qui en sort, qui paie quoi.",
        [
            "**Résumé** : rentrées, dépenses communes, perso et épargne de Bruno, différence, solde réel",
            "**Qui met quoi** (par origine) et **Qui a payé** (par carte, prélèvements)",
            "**Où part l'argent du foyer** et l'évolution sur l'année",
            "**Opérations du mois** (corrigeables) et **Opérations exceptionnelles**",
        ],
        [
            "corrige un libellé ou une catégorie dans **Opérations du mois**",
            "coche **Exceptionnel** pour sortir un gros montant ponctuel du budget courant",
        ],
        "Le relevé du commun contient le salaire de Bruno (2 614 €), ton virement de 950 €, le prêt (829 €) : « Qui met quoi » te montre 73 % Bruno, 27 % toi.",
    )
    _page(
        "💼 Phi Rising / 📸 Booth in Lyon — les activités",
        "Piloter une micro-entreprise : CA, cotisations URSSAF, dépenses, bénéfice.",
        [
            "mêmes 5 onglets que Budget Perso",
            "**Vue mensuelle** : CA brut, URSSAF, Dépenses, Bénéfices (avec le % de marge)",
            "dépenses par catégorie (avec variation) ; revenus par catégorie avec URSSAF et CA net",
            "**Vue globale** : alerte si le CA dépasse le seuil de la micro-entreprise",
        ],
        [
            "valide les **récurrences** du mois",
            "synchronise **Stripe** (page Sync) pour les paiements clients",
            "ajoute à la main les virements clients et les charges",
        ],
        "Phi Rising en octobre : CA brut 2 400 € (BNC), URSSAF 672 €, dépenses 180 € → bénéfice 1 548 €. Ce bénéfice est aussi compté dans les revenus de ton Budget Perso.",
    )
    _page(
        "🧮 Vue consolidée",
        "Tout sur une page : Perso, Phi Rising, Booth in Lyon et Foyer côte à côte.",
        [
            "revenus, dépenses et solde de chaque budget",
            "l'évolution de l'année, budget par budget",
            "le détail par compte réel (flux du mois + solde) et les mouvements internes",
        ],
        ["choisis l'année et le mois en haut de la page"],
        "Tu veux savoir ce que « rapporte » le mois : tu lis la colonne Total (Perso + Phi + Booth). Le Foyer est à part : il contient les revenus de Bruno.",
    )
    _page(
        "🏦 Patrimoine",
        "Voir ce que tu possèdes, compte par compte, et son évolution.",
        [
            "le patrimoine net total et par propriétaire",
            "la répartition par type de compte et le détail des comptes",
            "l'évolution des soldes dans le temps",
        ],
        [
            "les soldes se mettent à jour tout seuls à chaque import de relevé",
            "pour un compte non importé : **Mettre à jour un solde**",
            "corrige une erreur de saisie dans **Historique des soldes**",
        ],
        "Tu as noté 12 450 € sur le Livret : tu le saisis une fois par mois, le graphique d'évolution se construit.",
    )
    _page(
        "🧭 Règles",
        "Voir, corriger et tester les règles qui rangent automatiquement les opérations.",
        [
            "le tableau de toutes les règles : motif, budget visé, sens, catégorie, « Ranger dans », priorité, actif",
            "deux compteurs : **Opérations** (libellés reconnus) et **Appliquée à** (victoires)",
            "le nombre de règles **masquées** (battues par une plus prioritaire)",
        ],
        [
            "modifie, désactive ou supprime une règle, puis **Enregistrer**",
            "**Tester un libellé** pour voir quelle règle le range",
            "**Appliquer** les règles aux opérations déjà importées sans catégorie (aperçu avant)",
        ],
        "Les règles de départ du foyer (Leclerc, Carrefour…) ne s'appliquent qu'au **Foyer**. Pour ranger aussi tes achats perso chez Leclerc, tu crées une règle avec **Budget visé = Perso**.",
    )
    _page(
        "🔎 Transactions",
        "Retrouver n'importe quelle opération, la corriger, la déplacer, ou agir sur plusieurs d'un coup.",
        [
            "une liste de toutes les opérations, tous budgets confondus",
            "des filtres : période, budgets, comptes, recherche (sans accents), sens, catégories, montant, à vérifier, exceptionnelles, virements",
            "trois chiffres : nombre, rentrées, dépenses du résultat",
        ],
        [
            "corrige **libellé, budget, catégorie, exceptionnel** dans le tableau, puis **Enregistrer**",
            "coche des lignes (« Sél. ») puis applique un budget / une catégorie / « exceptionnel » à toutes",
            "exporte la recherche en CSV ; supprime avec confirmation",
        ],
        "Tu cherches « leclerc » sur « Tout » : 14 lignes. Tu les coches, Budget → Foyer, **Appliquer** : elles quittent ton budget perso.",
    )
    _page(
        "⚙️ Paramètres",
        "Régler les catégories, sauvegarder, vérifier les connexions.",
        [
            "**Catégories** : Liste (une case par budget), Remise en ordre, Renommer / fusionner",
            "**Sauvegarde** : un CSV de toutes tes opérations",
            "**Statut des connexions** et **Cache**",
        ],
        [
            "coche les budgets où une catégorie est proposée ; change son groupe",
            "applique la **Remise en ordre** (Médical → Santé…) en un clic",
            "télécharge une **sauvegarde** avant un gros changement",
        ],
        "Tu fusionnes « Repas » dans « Repas du midi » : les 84 opérations, les règles et les récurrences concernées sont mises à jour d'un coup.",
    )

# ===========================================================================
# SCÉNARIOS
# ===========================================================================
with tab_scenarios:
    st.markdown("Des cas concrets, avec les gestes exacts. Les montants sont des exemples.")

    st.subheader("Les achats par carte")
    _scenario(
        "🥖 Du pain avec ta carte du compte commun",
        "Le relevé du commun contient « PAIEMENT CB … MARIE BLACHERE CARTE 3935 » (3935 = ta carte). C'est sûrement une dépense du foyer, mais l'app ne connaît pas encore ce commerçant : elle te demande de confirmer.",
        [
            "Ouvre **À traiter** : la ligne est dans 🏠 Foyer, type 💳.",
            "Laisse l'Affectation sur **Foyer**, choisis la catégorie **Courses**.",
            "Coche **Règle** (motif « BLACHERE »), puis **Enregistrer**.",
        ],
        "La ligne est dans le budget du foyer, catégorie Courses. Les prochains achats chez ce commerçant avec ta carte seront classés **sans que tu aies rien à faire**. (Leclerc, Carrefour, SNCF, Matmut… sont déjà connus : ils ne te sont pas demandés.)",
    )
    _scenario(
        "🍔 Un achat perso avec ta carte du compte commun",
        "Tu as payé un Deliveroo avec la carte du commun : ce n'est pas une dépense du foyer, c'est la tienne.",
        [
            "Dans **À traiter**, sur la ligne 💳, passe l'**Affectation** sur **Perso**.",
            "Choisis la catégorie **Restaurants & bars**.",
            "Coche **Règle** pour que les prochains Deliveroo avec cette carte aillent seuls en Perso, puis **Enregistrer**.",
        ],
        "La dépense sort du foyer et entre dans ton **Budget Perso**. La règle créée range le commerçant en Perso et supprime la vérification pour lui.",
    )
    _scenario(
        "🧔 Les achats de Bruno avec sa carte (1295)",
        "Les paiements « CARTE 1295 » sont ceux de Bruno sur le compte commun.",
        [
            "Rien à faire : ils sont classés **Foyer** automatiquement et n'entrent pas dans ton budget.",
            "Si Bruno a fait un achat perso, classe-le dans la catégorie **Achats perso Bruno** ; son virement vers son épargne va dans **Épargne Bruno**.",
        ],
        "Ces deux catégories sont affichées **à part** des dépenses communes dans Budget Foyer.",
    )

    st.subheader("Les virements")
    _scenario(
        "🏠 Ta participation mensuelle de 950 € au compte commun",
        "Chaque mois, tu verses 950 € de ton compte pro vers le commun : loyer et charges.",
        [
            "N'enregistre **rien à la main**. Le virement arrive dans le relevé du commun.",
            "Dans **À traiter** : ligne ↘️ « Ta participation », catégorie déjà **Participation Charlotte**. Clique sur **Enregistrer**.",
        ],
        "Dans le **foyer**, c'est une rentrée. Dans ton **Budget Perso**, l'app crée la dépense « Participation foyer » (catégorie Loyer), car ton revenu est déjà compté via le bénéfice de Phi Rising. Si tu l'avais saisie à la main dans les 10 jours, elle est rattachée, **sans doublon**.",
    )
    _scenario(
        "💼 → 👤 Ton virement du compte pro vers BoursoBank",
        "Tu te verses de l'argent de ton compte pro vers ton compte perso pour tes dépenses du mois.",
        [
            "Il apparaît dans le relevé BoursoBank. Dans **À traiter**, bloc 🔁 Virement interne.",
            "L'**Autre compte** est déjà rempli : *Compte pro coaching*. Vérifie, puis **Enregistrer**.",
        ],
        "C'est un **virement interne** : ni une dépense ni un revenu supplémentaire (ton revenu est déjà compté via le bénéfice de Phi Rising). L'écriture côté pro est créée pour toi.",
    )
    _scenario(
        "🐖 Un virement vers ton Livret",
        "Tu mets 300 € de côté sur ton Livret.",
        [
            "Si tu importes aussi le relevé du Livret, les deux côtés sont **reliés automatiquement**.",
            "Sinon, il arrive dans **À traiter** (🔁), avec le Livret proposé comme autre compte : **Enregistrer**.",
        ],
        "Le virement n'est pas une dépense : il est compté dans la ligne **Épargne** de ton Budget Perso et réduit ton « Total fin du mois ».",
    )
    _scenario(
        "↩️ Un virement rejeté par la banque",
        "Tu vois « VIR INST … » suivi de « REJ VIR INST … » du même montant : la banque a refusé le virement puis rendu l'argent.",
        ["Rien à faire."],
        "L'app **annule les deux lignes entre elles** (elles sont marquées virement interne) : aucun effet sur les budgets, et le solde reste juste.",
    )
    _scenario(
        "⚠️ Une erreur bancaire (aller-retour de 695 €)",
        "La banque a viré par erreur de l'argent du compte pro vers le commun, puis il est revenu : ça n'aurait jamais dû exister.",
        [
            "**Ne supprime pas** la ligne : elle a vraiment bougé le solde du compte.",
            "Dans **À traiter**, passe son Affectation sur **Virement interne** et choisis l'**Autre compte** (ton compte pro).",
            "Variante : coche **Exceptionnel** (Budget Foyer → Opérations du mois).",
        ],
        "L'argent sorti est compensé : aucun budget n'est touché, et le **contrôle des comptes** reste ✅.",
    )

    st.subheader("Les cas particuliers")
    _scenario(
        "🎁 Une grosse rentrée ponctuelle (cagnotte du mariage, caution rendue)",
        "2 107 € arrivent sur le commun pour le mariage, et 1 230 € de caution : ça n'arrivera pas tous les mois.",
        [
            "À partir de **1 000 €**, l'app coche déjà **Exceptionnel** pour toi.",
            "Sous ce seuil : **Budget Foyer → Opérations du mois**, coche **Exceptionnel**, puis **Enregistrer les corrections**.",
        ],
        "La ligne n'entre plus dans le résumé du mois ni dans les graphiques (qui ne seraient plus comparables d'un mois à l'autre), mais elle reste dans le **solde réel**. Elle est listée dans « Opérations exceptionnelles ».",
    )
    _scenario(
        "📅 Une dépense annuelle (assurance, taxe)",
        "Tu paies 420 € d'assurance une fois par an.",
        ["Classe-la normalement (ex. **Assurance habitation**). **Ne la coche pas** « Exceptionnel »."],
        "Elle revient chaque année : elle fait partie de ton budget. Elle crée simplement un pic dans son mois.",
    )
    _scenario(
        "💵 Une dépense en espèces",
        "Tu paies 15 € en espèces : aucun relevé ne la contiendra.",
        [
            "**💰 Budget Perso → Transactions** : clique sur **➕ Ajouter une transaction**, remplis la ligne, **Enregistrer**.",
        ],
        "C'est le seul cas où tu saisis à la main une dépense perso : tout le reste vient des relevés.",
    )
    _scenario(
        "🔁 Une opération déjà saisie à la main, puis importée",
        "Tu avais noté « Courses 43 € » lundi ; le relevé l'apporte jeudi.",
        ["Importe le relevé normalement."],
        "Même montant à ±4 jours : l'app **rattache** le relevé à ta saisie au lieu de créer une deuxième ligne. Ton libellé et ta catégorie sont gardés.",
    )

    st.subheader("Corriger et entretenir")
    _scenario(
        "🔎 Retrouver et corriger des opérations après coup",
        "Tu t'aperçois que tous tes « Leclerc » du mois sont rangés en Perso alors que c'est le foyer.",
        [
            "Page **🔎 Transactions**, période *Tout* (ou le mois), recherche « leclerc ».",
            "Coche les lignes dans la colonne **Sél.**.",
            "Plus bas : **Budget → Foyer**, puis **Appliquer aux N ligne(s)**.",
        ],
        "Les lignes quittent le budget perso. Si une catégorie n'existe pas dans le foyer pour certaines, l'app te le dit et ne touche pas à celles-là.",
    )
    _scenario(
        "🧹 Aligner tes anciennes catégories sur la liste commune",
        "Ton historique contient « Médical », « Repas », « Restau / Soirées »…",
        [
            "**⚙️ Paramètres → Catégories → Remise en ordre**.",
            "Décoche les renommages que tu ne veux pas ; vérifie le nombre d'opérations concernées.",
            "Clique sur **Appliquer**. Fais d'abord une **sauvegarde** (Paramètres → Sauvegarde).",
        ],
        "Toutes les opérations, règles et récurrences concernées sont mises à jour d'un coup : « Médical » devient « Santé » partout. Les catégories protégées (Épargne, BNC, BIC, ND, Évenement Privé, Stripe) ne sont jamais renommées.",
    )
    _scenario(
        "🧭 Une règle range mal certaines opérations",
        "Une règle range des opérations qu'elle ne devrait pas, ou une règle ne se déclenche jamais.",
        [
            "Page **🧭 Règles** : regarde « Appliquée à » et le compteur de règles **masquées**.",
            "Utilise **Tester un libellé** avec le texte du relevé pour voir quelle règle gagne.",
            "Corrige le motif, le budget visé ou la priorité, puis **Enregistrer**.",
        ],
        "Une règle qui a des opérations mais « Appliquée à » = 0 est battue par une règle plus prioritaire : monte sa priorité ou supprime l'autre.",
    )
    _scenario(
        "✅ Le contrôle des comptes affiche ⚠️",
        "« Compte commun : écart de −47 € ».",
        [
            "Ouvre le **Détail** : il indique la période concernée.",
            "Page **🔎 Transactions**, filtre sur ce compte et cette période : cherche ce qui manque ou ce qui est en trop.",
            "Dépose de nouveau le relevé de cette période sur **Sync** : les opérations manquantes sont ajoutées, sans doublon.",
        ],
        "Cause fréquente : une période non importée, une opération supprimée, ou une saisie manuelle qui ne correspond à rien sur le compte.",
    )
    _scenario(
        "💼 Le début de mois côté pro",
        "C'est le 1er du mois : il faut mettre à jour Phi Rising et Booth in Lyon.",
        [
            "**💼 Phi Rising → Récurrences** : dans *À valider ce mois-ci*, valide les modèles.",
            "**🔄 Sync → Stripe** : synchronise les paiements du mois.",
            "**Vue mensuelle** : lis le CA brut, l'URSSAF estimée et le bénéfice.",
        ],
        "Le bénéfice de Phi Rising alimente tes revenus dans Budget Perso.",
    )

# ===========================================================================
# LEXIQUE
# ===========================================================================
with tab_lexicon:
    st.markdown(
        """
| Mot | Ce que ça veut dire |
|---|---|
| **Affectation / Budget** | Le budget où compte une opération : Perso, Foyer, Phi Rising ou Booth in Lyon. Une opération n'en a qu'un. |
| **Catégorie** | Le type de dépense ou de revenu (Courses, Loyer, Salaire…). Chaque budget a sa liste, en grande partie commune. |
| **Groupe** | Un regroupement de catégories (Logement, Alimentation, Transport…), pour lire les graphiques à deux niveaux. |
| **Règle** | « Si le libellé contient X, alors catégorie Y (et budget Z) ». Elle s'applique à l'import. |
| **Motif** | Le texte cherché dans le libellé par une règle (ex. LECLERC). |
| **Priorité** | L'ordre des règles : quand plusieurs s'appliquent, la plus haute gagne. |
| **Libellé banque** | Le texte brut de la banque. Le **libellé** affiché peut être nettoyé ou renommé par toi. |
| **À vérifier** 🔎 | Une opération qui demande une décision : ta carte sur le commun, ta participation, un virement. |
| **Virement interne** 🔁 | De l'argent déplacé entre deux de tes comptes : ni dépense ni revenu. |
| **Participation** | Ton virement mensuel au compte commun. C'est une rentrée du foyer et ta dépense « Loyer » dans ton budget perso. |
| **Exceptionnel** | Une opération ponctuelle et importante, sortie du budget courant mais gardée dans le solde. |
| **Contrôle des comptes** | La vérification que les opérations de l'app expliquent la variation réelle du solde de la banque. |
| **Récurrence** | Un modèle d'opération (abonnement, salaire) validé chaque mois. |
| **Bénéfice (Phi Rising)** | CA − URSSAF − dépenses. Il compte comme revenu dans ton budget perso. |
| **URSSAF** | Les cotisations de micro-entrepreneur, estimées au taux de chaque catégorie de revenu. |
| **Importée / saisie à la main** | Une opération venue d'un relevé, ou notée par toi. Une saisie est rattachée au relevé correspondant. |
| **✨** | Une catégorie suggérée d'après tes choix passés. À vérifier. |
"""
    )

# ===========================================================================
# DÉPANNAGE & LIMITES
# ===========================================================================
with tab_help:
    st.header("Dépannage")
    for question, answer in [
        (
            "Je n'arrive plus à me connecter (erreur de réseau ou de DNS)",
            "Le projet Supabase gratuit se met **en pause après environ une semaine d'inactivité**. Va sur le tableau de "
            "bord Supabase et restaure le projet : la connexion revient quelques minutes plus tard.",
        ),
        (
            "L'app n'affiche pas la dernière version après une mise à jour",
            "Sur Streamlit Cloud, utilise **Reboot app** : attendre ne suffit pas toujours.",
        ),
        (
            "Je ne trouve pas une opération",
            "Page **🔎 Transactions** : période *Tout*, recherche par mot du libellé. Elle est peut-être dans un autre budget "
            "(Foyer au lieu de Perso) ou comptée comme virement interne (active « Inclure les virements internes »).",
        ),
        (
            "Mon import affiche « 0 nouvelle »",
            "C'est normal si le relevé a déjà été importé : les opérations connues sont ignorées. Vérifie la période du fichier.",
        ),
        (
            "Une catégorie manque dans la liste déroulante",
            "Elle n'existe pas pour ce budget ou ce sens (dépense / revenu). **⚙️ Paramètres → Catégories → Liste** : coche le budget concerné.",
        ),
        (
            "Un chiffre de mon budget me semble faux",
            "Cherche une opération mal affectée (Foyer / Perso), un virement non reconnu (compté comme dépense), ou une saisie "
            "en double d'un relevé. La page **🔎 Transactions** permet de tout passer en revue.",
        ),
        (
            "J'ai supprimé quelque chose par erreur",
            "Une opération importée **réapparaît** si tu redéposes le même relevé. Sinon, utilise la **sauvegarde CSV** "
            "(Paramètres) : elle contient toutes tes opérations.",
        ),
    ]:
        with st.expander(question):
            st.markdown(answer)

    st.header("Ce que l'app ne fait pas (encore)")
    st.markdown(
        """
- **Les remboursements** : un achat remboursé compte pour l'instant comme un **revenu** (il gonfle les revenus du mois) au lieu
  de réduire la dépense. À venir.
- **L'indicateur « Exceptionnel »** n'est pris en compte que dans le **Foyer**. Dans Perso et les activités pro, il n'y a pas
  d'équivalent pour l'instant.
- **Les projets** (« Mariage », « Maison ») ne sont pas des étiquettes : on ne peut pas encore voir ce qu'un projet a rapporté
  et coûté.
- **La synchronisation bancaire automatique** : les relevés se déposent à la main (CSV). C'est une piste à étudier si la
  routine hebdomadaire devient pesante.
- **Les comptes pro** ne s'importent pas : ils se saisissent à la main, avec les récurrences et Stripe.
"""
    )
    st.header("Bonnes habitudes")
    st.markdown(
        """
- Fais le point **une fois par semaine** plutôt qu'une grosse fois par mois : les relevés sont courts et tu te souviens des achats.
- Prends l'habitude de cocher **Règle** pour les commerçants habituels : c'est ce qui fait baisser ton travail.
- Avant un gros changement (suppression en groupe, remise en ordre), fais une **sauvegarde**.
- Ne saisis **pas à la main** ce qui arrive par un relevé, ni tes virements entre comptes : ils sont reconnus à l'import.
"""
    )
