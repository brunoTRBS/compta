"""Textes d'aide des bulles ℹ️ : un résumé de ce que fait chaque page, chaque onglet, chaque bloc.

Données pures (aucun import Streamlit) : un test vérifie que chaque bulle posée dans l'app
a bien son texte ici. Le guide complet, avec des exemples, est dans la page « Guide ».
"""

HELP: dict[str, str] = {
    # ------------------------------------------------------------------ accueil
    "accueil": """
**À quoi sert l'app** : suivre ton argent sans rien noter à la main. Tu déposes les relevés
de la banque, l'app range chaque ligne, et tu corriges seulement ce qui est faux.

**Chaque semaine, 3 gestes** : 🔄 **Importer** (déposer les CSV) → 📥 **À classer** (dire pour qui
chaque ligne compte) → 👀 **Regarder** les budgets.

👉 La page **Guide** explique tout, page par page, avec des exemples.
""",
    # ------------------------------------------------------------------ à classer
    "a_traiter": """
**Les lignes qui attendent un geste** après un import.

**Pour chaque ligne**, regarde trois choses :
- **Payé avec** : le compte d'où vient la ligne (tu ne le changes pas) ;
- **Ça compte pour** : 🏠 Notre foyer, 👤 Moi, 💼 Phi Rising, 📸 Booth in Lyon, ou 🔁 un virement
  entre tes comptes. Tout ce qui vient du compte commun compte pour le foyer, **sauf si tu le changes** ;
- **Catégorie** : ✨ veut dire qu'elle est déjà proposée.

Puis clique sur **✅ Enregistrer**. Les lignes que tu ne touches pas sont validées telles quelles.

**Pareil la prochaine fois** : coche-la pour que les prochaines lignes avec le même mot se rangent
toutes seules (au même endroit, avec la même catégorie).

**Plus de détails** : libellé de la banque, mot reconnu, « ne pas compter dans le mois ».
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

Après l'import, un bandeau te renvoie vers **À classer** pour ranger ce qui reste.
""",
    "sync_banque": """
**Dépose un ou plusieurs relevés CSV** (BoursoBank, Crédit Mutuel, Hello Bank). Le compte est reconnu
automatiquement ; la première fois, l'app te demande à quel compte il correspond et s'en souvient.

**Aperçu avant import** : opérations lues, déjà importées, déjà saisies à la main, nouvelles. Déplie
la liste pour voir ce que chacune deviendra (🏠 Notre foyer, ↘️ Ta part du foyer, 🔁 Virement entre mes comptes, 💰 Budget).

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

Trois onglets : **Transactions** (corriger), **Vue mensuelle** (le bilan du mois) et
**Vue globale** (plusieurs mois).

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
    "virement": """
**Un virement entre deux de tes comptes** n'est ni une dépense ni un revenu : il déplace de
l'argent. Saisis-le ici si les deux comptes ne sont pas importés.

Avec les relevés importés, c'est **automatique** : les virements sont reconnus et, s'il en manque un
côté, ils arrivent dans **À classer**. Si tu en saisis un ici, fais-le **avant** l'import du relevé,
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

Tout ce qui vient du compte commun compte ici, sauf ce que tu as passé en **👤 Moi** dans À classer
(un achat perso, par exemple).
""",
    "foyer_operations": """
**Corriger les opérations du mois.** Modifie un libellé ou une catégorie, ou coche
**Ne pas compter dans le mois** pour sortir une ligne du budget courant sans la supprimer (le solde du compte
reste juste).

Pour déplacer une ligne vers un autre budget, utilise la page **Transactions** (colonne Budget).
""",
    "foyer_exceptionnelles": """
**Les opérations hors budget courant** : apport, caution rendue, cadeaux de mariage, erreur bancaire…
Elles ne comptent pas dans le résumé du mois ni dans les graphiques, mais restent dans le solde réel.

Décoche **Ne pas compter dans le mois** pour en remettre une dans le budget. L'app le propose d'office
à partir de 1 000 € (sauf salaire, participation et prêt).
""",
    # ------------------------------------------------------------------ pro
    "pro_page": """
**Une activité pro** (micro-entreprise) : chiffre d'affaires, cotisations URSSAF, dépenses et
bénéfice. Tu peux importer le relevé de la banque (Hello Bank) ou saisir à la main, avec la
synchro Stripe.

Cinq onglets : **Transactions**, **Virement**, **Vue mensuelle**, **Vue globale** et
**Simulateur** (prévoir les mois à venir).
""",
    "pro_transactions": """
**Les opérations de l'activité**, en dépenses (↓) et revenus (↑). Corrige, ajoute ou supprime.

Le **CA** vient des paiements Stripe et des virements clients.
**⚡ Catégoriser auto** applique les règles aux lignes sans catégorie.

Tes virements vers ton perso ne sont **pas des dépenses** de l'activité. S'ils apparaissent sur ton
relevé BoursoBank, **À classer** crée l'écriture côté pro pour toi.
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
    "pro_simulateur": """
**Un calculateur pour prévoir tes mois à venir.** Ajoute des prestations (mois, type de revenu,
montant) : l'app calcule l'URSSAF avec **les mêmes taux que tes vrais chiffres** et te montre ce
qu'il te reste après tes charges.

- **Charges pro par mois** : proposées d'après tes 3 derniers mois, modifiables.
- **Frais Stripe** : à saisir si le client paie par Stripe, ils réduisent la base de l'URSSAF.
- Une alerte prévient si ton CA de l'année dépasse le plafond de la micro-entreprise.

**Rien n'est enregistré** : c'est un brouillon, il se réinitialise quand tu quittes la page.
""",
    # ------------------------------------------------------------------ vue consolidée
    "vue_consolidee": """
**Tout sur une page** : Moi, Phi Rising, Booth in Lyon et Notre foyer côte à côte.

- **Résumé** : revenus, dépenses et solde de chaque budget. Le **foyer n'est pas additionné** au
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

Toutes les opérations, règles concernées sont mises à jour d'un coup.
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
« À classer » ont la priorité 200.

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
vérifier, hors du mois, virements.

**Corriger** dans le tableau : libellé, **Budget** (pour déplacer une opération d'un budget à
l'autre), catégorie, ne pas compter dans le mois. Puis **Enregistrer**.

Le tableau affiche les 300 plus récentes du résultat : affine les filtres pour voir les autres.
""",
    "transactions_actions": """
**Appliquer un changement à plusieurs lignes** : coche-les dans la colonne « Sél. », puis choisis un
budget, une catégorie ou « ne pas compter dans le mois ».

**Supprimer** demande une confirmation. Une opération importée d'un relevé réapparaîtrait si tu
redéposes le même relevé : pour la sortir des budgets, préfère « Ne pas compter dans le mois ».
""",
}
