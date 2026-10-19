"""Textes d'aide des bulles ℹ️ : un résumé de ce que fait chaque page, chaque onglet, chaque bloc.

Données pures (aucun import Streamlit) : un test vérifie que chaque bulle posée dans l'app
a bien son texte ici. Le guide complet, avec des exemples, est dans la page « Guide ».
"""

HELP: dict[str, str] = {
    # ------------------------------------------------------------------ accueil
    "accueil": """
**À quoi sert l'app** : suivre ton argent sans rien noter à la main. Tu déposes les relevés
de la banque, l'app range chaque opération, et tu corriges seulement ce qui est faux.

**Ta routine** : 🔄 **Sync** (déposer les CSV) → 📥 **À traiter** (valider) → regarder les budgets.

👉 La page **Guide** explique tout, page par page, avec des exemples.
""",
    # ------------------------------------------------------------------ à traiter
    "a_traiter": """
**La boîte de réception** : tout ce qui demande un geste après un import.

**Une ligne arrive ici si** : elle n'a pas de catégorie (🏷️), c'est un paiement avec ta carte sur
le compte commun (💳), c'est ta participation (↘️), ou un virement entre tes comptes (🔁).

**Ce que tu fais** : corrige l'**Affectation** (le budget où la ligne compte) et la **Catégorie**
si besoin, puis clique sur **✅ Enregistrer**. Les lignes à vérifier laissées telles quelles sont
validées.

**Règle** : coche-la pour que les prochaines opérations avec ce motif se rangent seules (même
dans un autre budget si tu as changé l'affectation).

✨ = catégorie suggérée d'après tes choix passés.
""",
    "controle_comptes": """
**Le contrôle des comptes** vérifie que l'app a bien **toutes** les opérations de chaque compte.

À chaque import, elle note le solde réel du relevé. Entre deux relevés, tes opérations doivent
expliquer exactement la variation du solde.

- ✅ **complet** : rien ne manque.
- ⚠️ **écart de X €** : il manque quelque chose (période non importée, ligne supprimée) ou une
  saisie ne correspond à rien. Le détail par période est dans « Détail ».
- 🆕 : un seul relevé pour l'instant, le contrôle commence au prochain.
""",
    # ------------------------------------------------------------------ sync
    "sync": """
**Importer** tes relevés bancaires (CSV) et tes paiements Stripe.

Les opérations déjà importées ou déjà saisies à la main ne sont **jamais recréées** : tu peux
déposer deux fois le même relevé sans risque.

Après l'import, un bandeau te renvoie vers **À traiter** pour valider ce qui reste.
""",
    "sync_banque": """
**Dépose un ou plusieurs relevés CSV** (BoursoBank, Crédit Mutuel). Le compte est reconnu
automatiquement ; la première fois, l'app te demande à quel compte il correspond et s'en souvient.

**Aperçu avant import** : opérations lues, déjà importées, déjà saisies à la main, nouvelles. Déplie
la liste pour voir ce que chacune deviendra (🏠 Foyer, 🔎 À vérifier, 🔁 Virement interne, 💰 Budget).

Clique ensuite sur **Importer**. Crédit Mutuel : garde le nom de fichier d'origine, c'est le numéro
de compte.
""",
    "sync_stripe": """
**Synchronise tes paiements Stripe** (chiffre d'affaires de Phi Rising ou Booth in Lyon) depuis la
date choisie. Les paiements déjà présents ne sont pas recréés.
""",
    # ------------------------------------------------------------------ budget perso
    "perso_page": """
**Ton budget personnel** : revenus, dépenses et épargne de **ton** argent (compte perso, Livret,
et ta part du foyer).

Cinq onglets : **Transactions** (corriger), **Récurrences**, **Virement**, **Vue mensuelle**
(le bilan du mois) et **Vue globale** (plusieurs mois).

Tes revenus comptent le **bénéfice de Phi Rising**, les virements reçus de Booth in Lyon et les
retraits du Livret. Un virement vers le Livret compte comme **Épargne**.
""",
    "perso_transactions": """
**Les opérations du mois**, en deux tableaux : dépenses (↓) et revenus (↑).

Tu peux **corriger** un libellé, un montant ou une catégorie, **ajouter** une opération à la main
(espèces) et **supprimer**. **⚡ Catégoriser auto** applique les règles aux lignes sans catégorie.

Les relevés importés arrivent tout seuls : n'ajoute à la main que ce qui n'est sur aucun relevé.
Pour chercher dans tous les budgets, utilise la page **Transactions**.
""",
    "recurrences": """
**Une récurrence** est un modèle (loyer, abonnement, salaire…) que tu valides chaque mois en un
clic au lieu de tout retaper.

⚠️ Pour un compte **importé** (perso, commun), l'import apporte déjà ces opérations : une
récurrence en plus ferait un **doublon** si le montant varie. Réserve-les aux comptes que tu
saisis à la main (comptes pro).
""",
    "virement": """
**Un virement entre deux de tes comptes** n'est ni une dépense ni un revenu : il déplace de
l'argent. Saisis-le ici si les deux comptes ne sont pas importés.

Avec les relevés importés, c'est **automatique** : les virements sont reconnus et, s'il en manque un
côté, ils arrivent dans **À traiter**. Si tu en saisis un ici, fais-le **avant** l'import du relevé,
sinon il fera doublon.
""",
    "perso_mensuelle": """
**Le bilan du mois.**

- **Revenus** : tes revenus + le bénéfice de Phi Rising + les virements reçus.
- **Dépenses** : tes dépenses du mois, hors épargne.
- **Épargne** : la catégorie Épargne + les virements vers le Livret.
- **Différence** : revenus − dépenses − virements vers le Livret.
- **Reste mois précédent** et **Total fin du mois** : le cumul depuis le début du suivi.

Plus bas, **Où part l'argent** détaille les dépenses.
""",
    "perso_globale": """
**Plusieurs mois d'un coup.** Choisis une période : tu obtiens les dépenses et les revenus par
catégorie et par mois (un tableau croisé), et la courbe revenus / dépenses.

Pratique pour repérer une catégorie qui grossit ou comparer deux périodes.
""",
    "repartition": """
**Où part l'argent.** Les barres montrent tes dépenses **par groupe** (Logement, Alimentation…),
la plus grosse en haut, avec le montant et la part.

Choisis un groupe dans « Détail d'un groupe » pour voir ses catégories dans le tableau. La colonne
**Variation** (▲▼) compare avec la période précédente.

Une couleur fixe par groupe, la même partout.
""",
    # ------------------------------------------------------------------ budget foyer
    "foyer": """
**Le budget du foyer** : le compte commun (Crédit Mutuel), avec ce que Bruno et toi y mettez et ce
qui en sort. Il se remplit tout seul depuis le relevé du commun.

- **Résumé** : rentrées, dépenses communes, perso et épargne de Bruno, différence, solde réel.
- **Qui met quoi** / **Qui a payé** : les rentrées par origine, les dépenses par carte.
- **Opérations du mois** : pour corriger une ligne.

Tes achats perso faits avec la carte du commun n'y figurent pas : ils sont dans ton budget perso.
""",
    "foyer_operations": """
**Corriger les opérations du mois.** Modifie un libellé ou une catégorie, ou coche
**Exceptionnel** pour sortir une ligne du budget courant sans la supprimer (le solde du compte
reste juste).

Pour déplacer une ligne vers ton budget perso, utilise la page **Transactions** (colonne Budget).
""",
    "foyer_exceptionnelles": """
**Les opérations hors budget courant** : apport, caution rendue, cadeaux de mariage, erreur bancaire…
Elles ne comptent pas dans le résumé du mois ni dans les graphiques, mais restent dans le solde réel.

Décoche **Exceptionnel** pour en remettre une dans le budget. L'app propose d'office « exceptionnel »
à partir de 1 000 € (sauf salaire, participation et prêt).
""",
    # ------------------------------------------------------------------ pro
    "pro_page": """
**Une activité pro** (micro-entreprise) : chiffre d'affaires, cotisations URSSAF, dépenses et
bénéfice. Ces comptes se saisissent à la main, avec les récurrences et la synchro Stripe.

Cinq onglets : **Transactions**, **Récurrences**, **Virement**, **Vue mensuelle**, **Vue globale**.
""",
    "pro_transactions": """
**Les opérations de l'activité**, en dépenses (↓) et revenus (↑). Corrige, ajoute ou supprime.

Le **CA** vient des paiements Stripe, des virements clients et des récurrences que tu valides.
**⚡ Catégoriser auto** applique les règles aux lignes sans catégorie.

Tes virements vers ton perso ne sont **pas des dépenses** de l'activité. S'ils apparaissent sur ton
relevé BoursoBank, **À traiter** crée l'écriture côté pro pour toi.
""",
    "pro_mensuelle": """
**Le bilan du mois de l'activité.**

- **CA brut** : le chiffre d'affaires encaissé.
- **URSSAF** : les cotisations estimées, au taux de chaque catégorie de revenu.
- **Dépenses** : les charges du mois.
- **Bénéfices** : CA − URSSAF − dépenses.

Dessous : les dépenses par catégorie (avec la variation) et les revenus par catégorie, avec
l'URSSAF et le CA net.
""",
    "pro_globale": """
**Plusieurs mois ou l'année complète** : revenus, dépenses et courbe par catégorie et par mois.

Une alerte s'affiche si le **CA dépasse le seuil de la micro-entreprise** sur l'année : dans ce
cas, consulte un expert-comptable.
""",
    # ------------------------------------------------------------------ vue consolidée
    "vue_consolidee": """
**Tout sur une page** : Perso, Phi Rising, Booth in Lyon et Foyer côte à côte.

- **Résumé** : revenus, dépenses et solde de chaque budget. Le **Foyer n'est pas additionné** au
  total (il contient les revenus de Bruno, et ta participation est déjà une dépense perso).
- **Évolution** de l'année, **détail par compte réel**, et **mouvements internes** du mois.
""",
    # ------------------------------------------------------------------ patrimoine
    "patrimoine": """
**Ce que tu possèdes**, compte par compte : comptes courants, Livret, pro.

Les soldes se mettent à jour **tout seuls** à chaque import de relevé. Tu peux aussi saisir un solde
à la main (utile pour un compte non importé) et corriger l'historique en cas d'erreur.
""",
    "patrimoine_solde": """
**Mettre à jour un solde à la main** : choisis le compte et saisis son solde actuel. Un point est
ajouté à l'historique, daté d'aujourd'hui.

Pour un compte importé par relevé, c'est inutile : le solde est noté à chaque import.
""",
    # ------------------------------------------------------------------ paramètres
    "settings": """
**Réglages de l'app** : les catégories (liste commune, remise en ordre, renommage), une sauvegarde
de tes opérations, l'état des connexions et le cache.
""",
    "settings_categories": """
**Une liste de catégories commune** à Perso, Foyer et activités pro, pour pouvoir les comparer.
Chaque catégorie est rangée dans un **groupe** (Logement, Alimentation…) : les graphiques montrent
l'essentiel par groupe et le détail par catégorie.

Trois onglets : **Liste** (qui est proposée où), **Remise en ordre** (aligner l'historique) et
**Renommer / fusionner**.
""",
    "settings_liste": """
**Une ligne par catégorie**, une case par budget : coche les budgets où elle est proposée. Le groupe
se change dans la liste déroulante.

Décocher ne touche pas aux opérations déjà classées. Pour **changer un nom**, utilise l'onglet
« Renommer / fusionner ». Le formulaire du bas crée une nouvelle catégorie.
""",
    "settings_cleanup": """
**Remettre ton historique en ordre** : des renommages proposés (Médical → Santé, Repas → Repas du
midi…) avec le nombre d'opérations concernées. Décoche ceux que tu ne veux pas, puis **Appliquer**.

Toutes les opérations, règles et récurrences concernées sont mises à jour d'un coup.
""",
    "settings_rename": """
**Renommer une catégorie** pour tout l'historique. Si le nouveau nom **existe déjà**, les deux
catégories sont **fusionnées**.

Épargne, BNC, BIC, ND, Évenement Privé et Stripe sont protégées : des calculs en dépendent
(ligne Épargne, taux URSSAF, frais Stripe).
""",
    "settings_sauvegarde": """
**Une copie de toutes tes opérations** en CSV. À faire avant un gros changement (recatégorisation,
suppression en groupe). Range le fichier : il ne sert qu'en cas de problème.
""",
    "settings_statut": """
**L'état des connexions** (base de données, Stripe). Clique sur « Vérifier » : ✅ si tout répond.
Si la base ne répond pas, le projet Supabase gratuit est peut-être **en pause** (inactivité) : à
restaurer depuis son tableau de bord.
""",
    "settings_cache": """
**Le cache** garde les données 5 minutes pour que l'app reste rapide. Si un chiffre te semble
périmé après une modification, vide le cache.
""",
    # ------------------------------------------------------------------ règles
    "regles": """
**Les règles rangent automatiquement** les opérations importées dont le libellé contient leur
**motif** : elles donnent une catégorie et, si tu le précises, un autre budget.

Quand plusieurs règles s'appliquent, **la plus prioritaire gagne**. Les règles créées depuis
« À traiter » ont la priorité 200.

Deux compteurs par règle : **Opérations** (libellés reconnus) et **Appliquée à** (victoires). Une
règle avec des opérations mais 0 application est **masquée** par une plus prioritaire.
""",
    "regles_test": """
**Colle un libellé de ton relevé** : l'app dit quelle règle le rangerait, dans quelle catégorie et
quel budget. Pratique pour comprendre un classement surprenant ou vérifier une nouvelle règle.
""",
    "regles_apply": """
**Appliquer les règles à l'existant** : les nouveaux imports les appliquent déjà seuls. Ce bouton
range les opérations **sans catégorie** déjà en base, après un aperçu de ce qui changerait.
""",
    # ------------------------------------------------------------------ transactions
    "transactions": """
**Toutes tes opérations, tous budgets confondus.**

**Chercher** : période, budgets, comptes, texte (sans accents), sens, catégories, montant, à
vérifier, exceptionnelles, virements internes.

**Corriger** dans le tableau : libellé, **Budget** (pour déplacer une opération d'un budget à
l'autre), catégorie, exceptionnel. Puis **Enregistrer**.

Le tableau affiche les 300 plus récentes du résultat : affine les filtres pour voir les autres.
""",
    "transactions_actions": """
**Appliquer un changement à plusieurs lignes** : coche-les dans la colonne « Sél. », puis choisis un
budget, une catégorie ou le statut exceptionnel.

**Supprimer** demande une confirmation. Une opération importée d'un relevé réapparaîtrait si tu
redéposes le même relevé : pour la sortir des budgets, préfère « Exceptionnel ».
""",
}
