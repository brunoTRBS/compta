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
    "🚀 Démarrer", "📅 Ma routine", "🧭 Page par page", "🎬 Exemples", "📖 Les mots", "🛟 Dépannage & limites",
])

# ===========================================================================
# DÉMARRER
# ===========================================================================
with tab_start:
    st.header("Chaque semaine, 3 gestes")
    st.markdown(
        """
1. **🔄 Importer** : tu télécharges les relevés de tes banques (fichiers **CSV**) et tu les déposes.
2. **📥 À classer** : pour chaque ligne, tu dis **pour qui elle compte** et sa **catégorie**, puis tu cliques sur **Enregistrer**.
3. **👀 Regarder** : tu ouvres **Mon budget**, **Budget du foyer**, **Phi Rising** ou **Booth in Lyon**.

Tu n'écris plus rien à la main. Et plus tu coches **Pareil la prochaine fois**, moins il reste de lignes à classer.
"""
    )

    st.header("Le circuit")
    st.code(
        """
 Relevés CSV        🔄 Importer          📥 À classer                   Les budgets
 (tes banques) ─►   l'app lit les   ─►   pour chaque ligne :       ─►   👤 Mon budget   🏠 Budget du foyer
                    lignes, sans         « Ça compte pour » +           💼 Phi Rising    📸 Booth in Lyon
                    doublon              catégorie, puis Enregistrer          │
                                              ▲                              ▼
                                       🧭 Règles (l'app apprend)       🧮 Tout ensemble · 🏦 Patrimoine

 Pour corriger après coup : 🔎 Transactions      Pour les catégories et la sauvegarde : ⚙️ Paramètres
""",
        language=None,
    )

    st.header("Tes comptes")
    st.markdown(
        """
Chaque ligne a un **compte** (« Payé avec ») et un budget où elle **compte** (« Ça compte pour »).
Le compte propose un budget au départ ; **tu peux toujours le changer ligne par ligne**.

| Compte | Banque | Ça compte pour (au départ) | Comment il arrive |
|---|---|---|---|
| Compte perso | BoursoBank | 👤 **Moi** | relevé CSV |
| Compte commun | Crédit Mutuel | 🏠 **Notre foyer** | relevé CSV |
| Livret épargne | BoursoBank | 👤 Moi (épargne) | relevé CSV, ou solde saisi à la main |
| Compte pro coaching | Hello Bank | 💼 **Phi Rising** | relevé CSV (ou saisie à la main) |
| Compte pro photobooth | Revolut | 📸 **Booth in Lyon** | saisie à la main, pour l'instant |
"""
    )

    st.header("Les quatre budgets")
    st.markdown(
        """
- 👤 **Moi** : **ton** argent. Tes revenus comptent le **bénéfice de Phi Rising**, les virements reçus de
  Booth in Lyon et les retraits du Livret. Ta **part du foyer** y est une dépense (« Loyer »).
- 🏠 **Notre foyer** : le compte commun. Ce que Bruno et toi y mettez, et tout ce qui en sort (prêt, courses,
  assurances…).
- 💼 **Phi Rising** et 📸 **Booth in Lyon** : tes deux activités, avec chiffre d'affaires, URSSAF, dépenses et bénéfice.

Une ligne ne compte que dans **un seul** budget. Un achat perso payé avec la carte du commun ? Tu changes
« Ça compte pour » en **👤 Moi**. Une dépense payée avec le compte pro mais qui est pour toi ? Pareil.
"""
    )

    st.header("Première fois, pas à pas")
    st.markdown(
        """
1. **🔄 Importer** → dépose le CSV de **BoursoBank**. La première fois, l'app demande à quel compte il correspond :
   choisis *Compte perso (Boursobank)*. Elle s'en souviendra. Clique sur **Importer**.
2. Même chose avec le CSV du **Crédit Mutuel** (garde le nom de fichier d'origine : c'est le numéro du compte) et celui de **Hello Bank**.
3. **📥 À classer** → passe les lignes en revue, puis **Enregistrer**.
4. **⚙️ Paramètres → Catégories → Remise en ordre** → aligne tes anciennes catégories sur la liste commune.
5. **👤 Mon budget → Vue mensuelle** et **🏠 Budget du foyer** : tes chiffres du mois.
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
| 1 | Sites des banques | Télécharge les CSV (la période depuis le dernier import suffit : les doublons sont ignorés). |
| 2 | 🔄 **Importer** | Dépose les fichiers, regarde l'aperçu, clique sur **Importer**. |
| 3 | 📥 **À classer** | Pour chaque ligne fausse, change **Ça compte pour** ou **Catégorie**. Coche **Pareil la prochaine fois** pour un commerçant habituel. Clique sur **✅ Enregistrer**. |
| 4 | 📥 **À classer** (bas de page) | Vérifie le **Contrôle des comptes** : chaque compte doit être complet. |
| 5 | 👤 / 🏠 | Un coup d'œil à **Mon budget** et **Budget du foyer** : où part l'argent ce mois-ci ? |
"""
    )
    st.header("Chaque mois — côté pro")
    st.markdown(
        """
- **🔄 Importer → Stripe** : synchronise les paiements du mois pour chaque activité.
- **💼 Phi Rising / 📸 Booth in Lyon → Vue mensuelle** : contrôle le CA, l'URSSAF estimée et le bénéfice.
- **🧮 Simulateur** (dans chaque activité) : prévois les mois à venir.
- Ta **part du foyer** et tes virements entre comptes ne se saisissent pas à la main : ils arrivent par les relevés.
"""
    )
    st.header("Exemple : un dimanche soir")
    st.info(
        """
**20 h 00** — tu télécharges les CSV. **20 h 03** — tu les déposes sur Importer : *31 opérations lues, 18 déjà importées,
13 nouvelles*. **20 h 04** — **Importer**. **20 h 05** — À classer : 13 lignes. Tu changes 2 achats du commun en **👤 Moi**,
tu ranges « Boulangerie » en Courses avec **Pareil la prochaine fois** coché, tu cliques **Enregistrer**.
**20 h 10** — contrôle des comptes ✅. Terminé.
"""
    )

# ===========================================================================
# PAGE PAR PAGE
# ===========================================================================
with tab_pages:
    st.markdown("Déplie une page pour voir à quoi elle sert, ce que tu y vois, ce que tu y fais, et un exemple.")

    _page(
        "🔄 Importer — déposer tes relevés",
        "Lire les relevés bancaires (CSV) et les paiements Stripe. Ce qui est déjà importé ou déjà saisi à la main n'est jamais recréé.",
        [
            "une zone pour déposer un ou plusieurs CSV (BoursoBank, Crédit Mutuel, Hello Bank)",
            "pour chaque compte : opérations lues, déjà importées, déjà saisies à la main, nouvelles",
            "la liste des nouvelles opérations avec ce qu'elles deviendront (🏠 Notre foyer · ↘️ Ta part du foyer · 🔁 Virement entre mes comptes · 💰 Budget)",
            "un bandeau « N opérations à classer » après l'import",
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
        "📥 À classer — les lignes qui attendent",
        "Ranger en un seul endroit tout ce que l'import n'a pas pu décider seul.",
        [
            "**une seule liste**, avec pour chaque ligne : la date, **Payé avec** (le compte), le libellé, le montant",
            "**Ça compte pour** : 🏠 Notre foyer · 👤 Moi · 💼 Phi Rising · 📸 Booth in Lyon · 🔁 Virement entre mes comptes",
            "**Catégorie** (✨ = déjà proposée d'après tes choix passés) et la case **Pareil la prochaine fois**",
            "**Plus de détails** : de / vers pour un virement, mot reconnu, libellé de la banque, « ne pas compter dans le mois »",
            "en bas : le **Contrôle des comptes** et un menu 🛠️ Outils",
        ],
        [
            "change **Ça compte pour** si le budget est faux (tout ce qui vient du compte commun compte pour le foyer, sauf si tu le changes)",
            "choisis la **Catégorie**",
            "coche **Pareil la prochaine fois** pour qu'une règle range les prochaines seules",
            "clique sur **✅ Enregistrer** : les lignes que tu n'as pas touchées sont validées telles quelles",
        ],
        "Une ligne « DELIVEROO » payée avec le compte commun arrive en 🏠 Notre foyer. Tu passes **Ça compte pour** sur **👤 Moi**, la catégorie sur *Restaurants & bars*, tu coches **Pareil la prochaine fois**. La prochaine fois, elle ira directement chez toi.",
    )
    _page(
        "👤 Mon budget",
        "Suivre ton argent : revenus, dépenses, épargne, reste du mois.",
        [
            "3 onglets : Transactions · Vue mensuelle · Vue globale",
            "**Vue mensuelle** : Revenus, Dépenses, Épargne, Différence, Reste du mois précédent, Total fin du mois",
            "**Où part l'argent** : barres par groupe, détail par catégorie, variation sur le mois précédent",
            "**Vue globale** : catégories × mois sur une période, courbe revenus / dépenses",
        ],
        [
            "corrige ou ajoute une opération à la main (espèces) dans **Transactions**",
            "choisis l'année et le mois en haut de la Vue mensuelle",
            "active **Ajouter les dépenses communes du foyer** pour la vue d'ensemble (ta part n'est comptée qu'une fois)",
        ],
        "En octobre : Revenus 3 120 €, Dépenses 1 480 €, Épargne 300 € → Différence 1 340 €. Tu vois que « Alimentation » monte de 12 % : tu ouvres le groupe pour voir quelle catégorie.",
    )
    _page(
        "🏠 Budget du foyer",
        "Suivre le compte commun : ce que vous y mettez, ce qui en sort, qui paie quoi.",
        [
            "**Résumé** : rentrées, dépenses communes, perso et épargne de Bruno, différence, solde réel",
            "**Qui met quoi** (par origine) et **Qui a payé** (par carte, prélèvements)",
            "**Où part l'argent du foyer** et l'évolution sur l'année",
            "**Opérations du mois** (corrigeables) et **Opérations hors du mois**",
        ],
        [
            "corrige un libellé ou une catégorie dans **Opérations du mois**",
            "coche **Ne pas compter dans le mois** pour sortir un gros montant ponctuel du budget courant",
        ],
        "Le relevé du commun contient le salaire de Bruno (2 614 €), ton virement de 950 €, le prêt (829 €) : « Qui met quoi » te montre 73 % Bruno, 27 % toi.",
    )
    _page(
        "💼 Phi Rising / 📸 Booth in Lyon — les activités",
        "Piloter une micro-entreprise : CA, cotisations URSSAF, dépenses, bénéfice, et prévoir les mois à venir.",
        [
            "5 onglets : Transactions · Virement · Vue mensuelle · Vue globale · **Simulateur**",
            "**Vue mensuelle** : CA brut, URSSAF, Dépenses, Bénéfices (avec le % de marge)",
            "dépenses par catégorie (avec variation) ; revenus par catégorie avec URSSAF et CA net",
            "**Vue globale** : alerte si le CA dépasse le seuil de la micro-entreprise",
        ],
        [
            "synchronise **Stripe** (page Importer) pour les paiements clients",
            "ajoute à la main les virements clients et les charges, ou importe le relevé (Hello Bank)",
            "utilise le **Simulateur** pour prévoir ce qu'il te restera",
        ],
        "Phi Rising en octobre : CA brut 2 400 € (BNC), URSSAF 672 €, dépenses 180 € → bénéfice 1 548 €. Ce bénéfice est aussi compté dans les revenus de Mon budget.",
    )
    _page(
        "🧮 Simulateur (dans chaque activité)",
        "Prévoir un mois : « si je fais ces prestations, combien me reste-t-il ? ». Rien n'est enregistré.",
        [
            "un tableau où tu ajoutes des prestations : mois, nom, type de revenu (BNC, BIC, ND…), montant, frais Stripe",
            "tes **charges pro par mois**, proposées d'après tes 3 derniers mois",
            "le total : chiffre d'affaires, URSSAF, charges, **ce qu'il te reste**, mois par mois",
            "une alerte si ton CA de l'année dépasse le plafond de la micro-entreprise",
        ],
        [
            "ajoute ou modifie des lignes (le « + » du tableau)",
            "ajuste les charges du mois ; coche le versement libératoire si tu y es",
        ],
        "Novembre : 3 séances à 300 € (BNC). URSSAF 252 € (28 %), charges 120 € → il te reste 528 €.",
    )
    _page(
        "🧮 Tout ensemble",
        "Tout sur une page : Moi, Phi Rising, Booth in Lyon et Notre foyer côte à côte.",
        [
            "revenus, dépenses et solde de chaque budget",
            "l'évolution de l'année, budget par budget",
            "le détail par compte réel (flux du mois + solde) et les mouvements internes",
        ],
        ["choisis l'année et le mois en haut de la page"],
        "Tu veux savoir ce que « rapporte » le mois : tu lis la colonne Total (Moi + Phi + Booth). Le foyer est à part : il contient les revenus de Bruno.",
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
            "le tableau de toutes les règles : mot reconnu, budget visé, sens, catégorie, « Ranger dans », priorité, actif",
            "deux compteurs : **Opérations** (libellés reconnus) et **Appliquée à** (victoires)",
            "le nombre de règles **masquées** (battues par une plus prioritaire)",
        ],
        [
            "modifie, désactive ou supprime une règle, puis **Enregistrer**",
            "**Tester un libellé** pour voir quelle règle le range",
            "**Appliquer** les règles aux opérations déjà importées sans catégorie (aperçu avant)",
        ],
        "Les règles de départ du foyer (Leclerc, Carrefour…) ne s'appliquent qu'à **Notre foyer**. Pour ranger aussi tes achats perso chez Leclerc, tu crées une règle avec **Budget visé = Moi**.",
    )
    _page(
        "🔎 Transactions",
        "Retrouver n'importe quelle opération, la corriger, la déplacer, ou agir sur plusieurs d'un coup.",
        [
            "une liste de toutes les opérations, tous budgets confondus",
            "des filtres : période, budgets, comptes, recherche (sans accents), sens, catégories, montant, à vérifier, hors du mois, virements",
            "trois chiffres : nombre, rentrées, dépenses du résultat",
        ],
        [
            "corrige **libellé, budget, catégorie, ne pas compter dans le mois** dans le tableau, puis **Enregistrer**",
            "coche des lignes (« Sél. ») puis applique un budget / une catégorie à toutes",
            "exporte la recherche en CSV ; supprime avec confirmation",
        ],
        "Tu cherches « leclerc » sur « Tout » : 14 lignes. Tu les coches, Budget → Notre foyer, **Appliquer** : elles quittent ton budget perso.",
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
        "Tu fusionnes « Repas » dans « Repas du midi » : les 84 opérations et les règles concernées sont mises à jour d'un coup.",
    )

# ===========================================================================
# EXEMPLES
# ===========================================================================
with tab_scenarios:
    st.markdown("Des cas concrets, avec les gestes exacts. Les montants sont des exemples.")

    st.subheader("Les achats par carte")
    _scenario(
        "🥖 Du pain avec ta carte du compte commun",
        "Le relevé du commun contient « PAIEMENT CB … MARIE BLACHERE CARTE 3935 ». L'app ne connaît pas encore ce commerçant : la ligne attend dans À classer, déjà rangée dans 🏠 Notre foyer.",
        [
            "Ouvre **À classer** : la ligne dit « Payé avec : Compte commun », « Ça compte pour : 🏠 Notre foyer ».",
            "Laisse **Notre foyer** et choisis la catégorie **Courses**.",
            "Coche **Pareil la prochaine fois**, puis **Enregistrer**.",
        ],
        "La ligne est dans le budget du foyer, catégorie Courses. Les prochains achats chez ce commerçant seront classés **sans que tu aies rien à faire**. (Leclerc, Carrefour, SNCF, Matmut… sont déjà connus : ils ne te sont pas demandés.)",
    )
    _scenario(
        "🍔 Un achat perso avec la carte du compte commun",
        "Tu as payé un Deliveroo avec la carte du commun : ce n'est pas une dépense du foyer, c'est la tienne.",
        [
            "Dans **À classer**, sur la ligne, change **Ça compte pour** en **👤 Moi**.",
            "Choisis la catégorie **Restaurants & bars**.",
            "Coche **Pareil la prochaine fois** pour que les prochains Deliveroo aillent seuls chez toi, puis **Enregistrer**.",
        ],
        "La dépense sort du foyer et entre dans **Mon budget**. Tu décides ligne par ligne : l'app ne devine pas qui a payé.",
    )
    _scenario(
        "💼 Une dépense payée avec le compte pro, mais qui est pour toi",
        "Tu as payé un cadeau avec la carte du compte pro. Ce n'est pas une charge de ton activité.",
        [
            "Dans **À classer**, la ligne arrive en 💼 Phi Rising (« Payé avec : Compte pro »).",
            "Change **Ça compte pour** en **👤 Moi** et choisis la catégorie.",
        ],
        "La dépense compte dans **Mon budget** et ne baisse pas le bénéfice de Phi Rising (qui compte déjà comme revenu chez toi) : elle n'est comptée qu'une fois.",
    )
    _scenario(
        "🧔 Les achats de Bruno avec sa carte (1295)",
        "Les paiements « CARTE 1295 » sont ceux de Bruno sur le compte commun.",
        [
            "Rien à faire : ils comptent pour 🏠 Notre foyer, comme tout le reste du compte commun.",
            "Si Bruno a fait un achat perso, mets-le dans la catégorie **Achats perso Bruno** ; son virement vers son épargne va dans **Épargne Bruno**.",
        ],
        "Ces deux catégories sont affichées **à part** des dépenses communes dans Budget du foyer.",
    )

    st.subheader("Les virements")
    _scenario(
        "🏠 Ta part du foyer : 950 € par mois sur le compte commun",
        "Chaque mois, tu verses 950 € vers le commun : loyer et charges.",
        [
            "N'enregistre **rien à la main**. Le virement arrive dans le relevé du commun.",
            "Dans **À classer** : ligne ↘️ « Ta part du foyer », catégorie déjà **Participation Charlotte** (✨). Clique sur **Enregistrer**.",
        ],
        "Pour le **foyer**, c'est une rentrée. Dans **Mon budget**, l'app crée la dépense « Participation foyer » (catégorie Loyer), car ton revenu est déjà compté via le bénéfice de Phi Rising. Si tu l'avais saisie à la main dans les 10 jours, elle est rattachée, **sans doublon**.",
    )
    _scenario(
        "💼 ➜ 👤 Ton virement du compte pro vers BoursoBank",
        "Tu te verses de l'argent de ton compte pro vers ton compte perso.",
        [
            "Il apparaît dans le relevé BoursoBank, avec **Ça compte pour : 🔁 Virement entre mes comptes**.",
            "Les colonnes **De** et **Vers** se lisent comme une phrase : *De : Compte pro → Vers : Compte perso*. Vérifie l'autre compte, puis **Enregistrer**.",
        ],
        "Ni une dépense ni un revenu en plus (ton revenu est déjà compté via le bénéfice de Phi Rising). L'écriture côté pro est créée pour toi.",
    )
    _scenario(
        "💼 ➜ 🏠 Un virement du compte pro vers le compte commun",
        "Tu verses 650 € du compte pro vers le commun.",
        [
            "Dans le relevé du pro : « Ça compte pour : 🔁 Virement entre mes comptes », *Vers : Compte commun*.",
            "Clique sur **Enregistrer**. Le côté du commun vient de son propre relevé (la ligne ↘️ Ta part du foyer).",
        ],
        "La ligne du pro ne compte ni en dépense ni en revenu.",
    )
    _scenario(
        "🐖 Un virement vers ton Livret",
        "Tu mets 300 € de côté sur ton Livret.",
        [
            "Si tu importes aussi le relevé du Livret, les deux côtés sont **reliés automatiquement**.",
            "Sinon, il arrive dans **À classer** (🔁), avec le Livret proposé comme autre compte : **Enregistrer**.",
        ],
        "Le virement n'est pas une dépense : il est compté dans la ligne **Épargne** de Mon budget et réduit ton « Total fin du mois ».",
    )
    _scenario(
        "↩️ Un virement rejeté par la banque",
        "Tu vois « VIR INST … » suivi de « REJ VIR INST … » du même montant : la banque a refusé le virement puis rendu l'argent.",
        ["Rien à faire."],
        "L'app **annule les deux lignes entre elles** : aucun effet sur les budgets, et le solde reste juste.",
    )
    _scenario(
        "⚠️ Une erreur bancaire (aller-retour de 695 €)",
        "La banque a viré par erreur de l'argent du compte pro vers le commun, puis il est revenu : ça n'aurait jamais dû exister.",
        [
            "**Ne supprime pas** la ligne : elle a vraiment bougé le solde du compte.",
            "Dans **À classer**, passe **Ça compte pour** sur **🔁 Virement entre mes comptes** et choisis l'autre compte (dans *Plus de détails*).",
            "Variante : coche **Ne pas compter dans le mois** (Budget du foyer → Opérations du mois).",
        ],
        "L'argent sorti est compensé : aucun budget n'est touché, et le **contrôle des comptes** reste ✅.",
    )

    st.subheader("Les cas particuliers")
    _scenario(
        "🎁 Une grosse rentrée ponctuelle (cagnotte du mariage, caution rendue)",
        "2 107 € arrivent sur le commun pour le mariage, et 1 230 € de caution : ça n'arrivera pas tous les mois.",
        [
            "À partir de **1 000 €**, l'app coche déjà **Ne pas compter dans le mois** pour toi.",
            "Sous ce seuil : **Budget du foyer → Opérations du mois**, coche **Ne pas compter dans le mois**, puis **Enregistrer les corrections**.",
        ],
        "La ligne n'entre plus dans le résumé du mois ni dans les graphiques, mais elle reste dans le **solde réel**. Elle est listée dans « Opérations hors du mois ».",
    )
    _scenario(
        "📅 Une dépense annuelle (assurance, taxe)",
        "Tu paies 420 € d'assurance une fois par an.",
        ["Classe-la normalement (ex. **Assurance habitation**). **Ne coche pas** « Ne pas compter dans le mois »."],
        "Elle revient chaque année : elle fait partie de ton budget. Elle crée simplement un pic dans son mois.",
    )
    _scenario(
        "💵 Une dépense en espèces",
        "Tu paies 15 € en espèces : aucun relevé ne la contiendra.",
        [
            "**👤 Mon budget → Transactions** : clique sur **➕ Ajouter une transaction**, remplis la ligne, **Enregistrer**.",
        ],
        "C'est le seul cas où tu saisis à la main une dépense perso : tout le reste vient des relevés.",
    )
    _scenario(
        "🔁 Une opération déjà saisie à la main, puis importée",
        "Tu avais noté « Courses 43 € » lundi ; le relevé l'apporte jeudi.",
        ["Importe le relevé normalement."],
        "Même montant à ±4 jours : l'app **rattache** le relevé à ta saisie au lieu de créer une deuxième ligne. Ton libellé et ta catégorie sont gardés.",
    )

    st.subheader("Prévoir, corriger et entretenir")
    _scenario(
        "🧮 Prévoir un mois côté pro",
        "Tu as trois séances prévues en novembre et tu veux savoir ce qu'il te restera.",
        [
            "Ouvre **💼 Phi Rising → Simulateur**.",
            "Dans le tableau, ajoute tes prestations : mois, nom, type de revenu (BNC), montant.",
            "Vérifie les **charges pro par mois** proposées, puis lis **Il te reste**.",
        ],
        "L'URSSAF est calculée avec les mêmes taux que tes vrais chiffres. Rien n'est enregistré : c'est un brouillon.",
    )
    _scenario(
        "🔎 Retrouver et corriger des opérations après coup",
        "Tu t'aperçois que tous tes « Leclerc » du mois sont rangés chez toi alors que c'est le foyer.",
        [
            "Page **🔎 Transactions**, période *Tout* (ou le mois), recherche « leclerc ».",
            "Coche les lignes dans la colonne **Sél.**.",
            "Plus bas : **Budget → Notre foyer**, puis **Appliquer aux N ligne(s)**.",
        ],
        "Les lignes quittent ton budget perso. Si une catégorie n'existe pas dans le foyer pour certaines, l'app te le dit et ne touche pas à celles-là.",
    )
    _scenario(
        "🧹 Aligner tes anciennes catégories sur la liste commune",
        "Ton historique contient « Médical », « Repas », « Restau / Soirées »…",
        [
            "**⚙️ Paramètres → Catégories → Remise en ordre**.",
            "Décoche les renommages que tu ne veux pas ; vérifie le nombre d'opérations concernées.",
            "Clique sur **Appliquer**. Fais d'abord une **sauvegarde** (Paramètres → Sauvegarde).",
        ],
        "Toutes les opérations et les règles concernées sont mises à jour d'un coup : « Médical » devient « Santé » partout. Les catégories protégées (Épargne, BNC, BIC, ND, Évenement Privé, Stripe) ne sont jamais renommées.",
    )
    _scenario(
        "🧭 Une règle range mal certaines opérations",
        "Une règle range des opérations qu'elle ne devrait pas, ou une règle ne se déclenche jamais.",
        [
            "Page **🧭 Règles** : regarde « Appliquée à » et le compteur de règles **masquées**.",
            "Utilise **Tester un libellé** avec le texte du relevé pour voir quelle règle gagne.",
            "Corrige le mot reconnu, le budget visé ou la priorité, puis **Enregistrer**.",
        ],
        "Une règle qui a des opérations mais « Appliquée à » = 0 est battue par une règle plus prioritaire : monte sa priorité ou supprime l'autre.",
    )
    _scenario(
        "✅ Le contrôle des comptes affiche ⚠️",
        "« Compte commun : écart de −47 € ».",
        [
            "Ouvre le **Détail** : il indique la période concernée.",
            "Page **🔎 Transactions**, filtre sur ce compte et cette période : cherche ce qui manque ou ce qui est en trop.",
            "Dépose de nouveau le relevé de cette période sur **Importer** : les opérations manquantes sont ajoutées, sans doublon.",
        ],
        "Cause fréquente : une période non importée, une opération supprimée, ou une saisie manuelle qui ne correspond à rien sur le compte.",
    )

# ===========================================================================
# LES MOTS
# ===========================================================================
with tab_lexicon:
    st.markdown(
        """
| Mot | Ce que ça veut dire |
|---|---|
| **Payé avec** | Le compte d'où vient la ligne (le relevé où elle apparaît). Tu ne le changes pas. |
| **Ça compte pour** | Le budget où la ligne compte : Notre foyer, Moi, Phi Rising ou Booth in Lyon. Une ligne n'en a qu'un. |
| **Virement entre mes comptes** 🔁 | De l'argent déplacé entre deux de tes comptes : ni dépense ni revenu. **De** = d'où il part, **Vers** = où il arrive. |
| **Catégorie** | Le type de dépense ou de revenu (Courses, Loyer, Salaire…). Chaque budget a sa liste, en grande partie commune. |
| **Groupe** | Un regroupement de catégories (Logement, Alimentation, Transport…), pour lire les graphiques à deux niveaux. |
| **Pareil la prochaine fois** | Crée une **règle** : les prochaines lignes avec le même mot seront rangées toutes seules. |
| **Règle** | « Si le libellé contient tel mot, alors telle catégorie (et tel budget) ». Elle s'applique à l'import. |
| **Mot reconnu** | Le texte cherché dans le libellé par une règle (ex. LECLERC). |
| **Priorité** | L'ordre des règles : quand plusieurs s'appliquent, la plus haute gagne. |
| **Libellé de la banque** | Le texte brut de la banque. Le **libellé** affiché peut être nettoyé ou renommé par toi. |
| **Ta part du foyer** ↘️ | Ton virement mensuel au compte commun. C'est une rentrée du foyer et ta dépense « Loyer » dans Mon budget. |
| **Ne pas compter dans le mois** | Une opération ponctuelle et importante, sortie du budget courant mais gardée dans le solde. |
| **Contrôle des comptes** | La vérification que les opérations de l'app expliquent la variation réelle du solde de la banque. |
| **Bénéfice (Phi Rising)** | CA − URSSAF − dépenses. Il compte comme revenu dans Mon budget. |
| **URSSAF** | Les cotisations de micro-entrepreneur, estimées au taux de chaque catégorie de revenu. |
| **Simulateur** | Un calculateur pour prévoir ce qu'il te restera, sans rien enregistrer. |
| **Importée / saisie à la main** | Une opération venue d'un relevé, ou notée par toi. Une saisie est rattachée au relevé correspondant. |
| **✨** | Une catégorie déjà proposée d'après tes choix passés. À vérifier d'un coup d'œil. |
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
            "(Notre foyer au lieu de Moi) ou comptée comme virement entre tes comptes (active « Inclure les virements »).",
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
            "Cherche une opération mal rangée (Notre foyer / Moi), un virement non reconnu (compté comme dépense), ou une saisie "
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
- **« Ne pas compter dans le mois »** n'est pris en compte que dans **Notre foyer**. Dans Mon budget et les activités pro, il n'y a pas
  d'équivalent pour l'instant.
- **Les projets** (« Mariage », « Maison ») ne sont pas des étiquettes : on ne peut pas encore voir ce qu'un projet a rapporté
  et coûté.
- **La synchronisation bancaire automatique** : les relevés se déposent à la main (CSV).
- **Le relevé du compte pro** (Hello Bank) se lit, mais l'URSSAF que tu paies et les versements Stripe sont déjà dans le calcul
  du bénéfice : les importer tels quels ferait un **doublon**. Revolut (Booth in Lyon) ne s'importe pas encore.
"""
    )
    st.header("Bonnes habitudes")
    st.markdown(
        """
- Fais le point **une fois par semaine** plutôt qu'une grosse fois par mois : les relevés sont courts et tu te souviens des achats.
- Prends l'habitude de cocher **Pareil la prochaine fois** pour les commerçants habituels : c'est ce qui fait baisser ton travail.
- Avant un gros changement (suppression en groupe, remise en ordre), fais une **sauvegarde**.
- Ne saisis **pas à la main** ce qui arrive par un relevé, ni tes virements entre comptes : ils sont reconnus à l'import.
"""
    )
