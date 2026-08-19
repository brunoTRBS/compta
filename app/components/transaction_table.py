"""Composant réutilisable : tableau de transactions éditable."""

from datetime import date, datetime

import polars as pl
import streamlit as st

from src.config import TransactionSource
from src.services.db_reader import invalidate_cache
from src.services.supabase import delete_transaction, insert_transaction, update_transaction


def render_editable_transactions(
    df: pl.DataFrame,
    business_id: str,
    key: str,
    categories_by_direction: dict[str, list[str]],
    account_id: str | None = None,
    account_options: dict[str, str] | None = None,
) -> None:
    """Tableau Revenus/Dépenses éditable, avec ajout de ligne directe.

    Le bouton "➕ Ajouter une transaction" insère une ligne vide en tête du
    tableau (le plus récent étant affiché en premier), remplie sur place.
    La suppression se fait via une case "🗑️ Supprimer" par ligne (pas le "−"
    natif du tableau, désactivé ici) + bouton de confirmation, immédiate (pas
    besoin d'Enregistrer). L'ajout/la modification, eux, passent par un seul
    bouton "Enregistrer" groupé (pas à chaque frappe : un appel réseau par
    caractère tapé ralentit tout et peut se faire doubler par la frappe
    suivante). Une ligne incomplète au clic (libellé/date/montant manquant)
    n'est jamais effacée en silence : elle reste affichée avec un message
    expliquant ce qu'il manque.

    Args:
        df: transactions de la période (colonnes id, date, label, amount, category,
            et account_id si account_options est fourni).
        business_id: activité fixe appliquée à toute nouvelle ligne créée ici.
        key: préfixe unique pour les clés de widgets.
        categories_by_direction: {"income": [...], "expense": [...]}.
        account_id: compte fixe pour les nouvelles lignes (page à 1 seul compte).
        account_options: {libellé affiché: id} si plusieurs comptes possibles —
            affiche une colonne Compte éditable. Mutuellement exclusif avec account_id.
    """
    tab_expense, tab_income = st.tabs(["↓ Dépenses", "↑ Revenus"])
    with tab_expense:
        _render_editable_direction(
            df.filter(pl.col("amount") < 0), "expense", business_id, f"{key}_expense",
            categories_by_direction.get("expense", []), account_id, account_options,
        )
    with tab_income:
        _render_editable_direction(
            df.filter(pl.col("amount") > 0), "income", business_id, f"{key}_income",
            categories_by_direction.get("income", []), account_id, account_options,
        )


def _render_editable_direction(
    direction_df: pl.DataFrame,
    direction: str,
    business_id: str,
    key: str,
    categories: list[str],
    account_id: str | None,
    account_options: dict[str, str] | None,
) -> None:
    origin_key = f"{key}_origin"
    if origin_key not in st.session_state:
        st.session_state[origin_key] = direction_df.to_dicts()

    pending_key = f"{key}_pending_new"
    if pending_key not in st.session_state:
        st.session_state[pending_key] = []

    undo_key = f"{key}_undo_snapshot"
    if undo_key not in st.session_state:
        st.session_state[undo_key] = []

    # Le data_editor mémorise ses propres modifications (ajouts/suppressions) sous
    # sa clé, indépendamment des données qu'on lui repasse à chaque rerun. Un
    # numéro de version dans la clé force un widget entièrement neuf après chaque
    # enregistrement — plus fiable qu'un del st.session_state après coup.
    version_key = f"{key}_version"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    # Dernier contenu édité connu (posé en fin de fonction) : sert à récupérer ce
    # que l'utilisateur a tapé dans les nouvelles lignes avant de forcer un
    # widget neuf (changement de version), pour ne pas perdre sa saisie en cours.
    last_edited_key = f"{key}_last_edited"

    def _carry_over_pending() -> None:
        prev = st.session_state.get(last_edited_key)
        if prev is None:
            return
        # Une ligne en attente (pas encore enregistrée, donc sans id) cochée "Supprimer"
        # est écartée ici plutôt que reportée : c'est le seul moment où ce cas est traité,
        # puisque delete_transaction() ne peut rien faire d'une ligne qui n'existe pas
        # encore en base. Sans ce filtre, une ligne fraîchement ajoutée et cochée pour
        # suppression réapparaissait au prochain ajout/suppression (elle était reportée
        # telle quelle, sans jamais regarder la case cochée).
        rows = [
            row for row in prev.iter_rows(named=True)
            if row.get("id") is None and not row.get("Supprimer")
        ]
        for row in rows:
            row.pop("Supprimer", None)
            # L'aller-retour par le data_editor (qui passe par pandas) renvoie un
            # datetime plutôt qu'un date pour cette colonne : sans cette
            # normalisation, la reconstruction du DataFrame avec le schéma
            # d'origine (colonne "date" typée Date) plante avec un ComputeError.
            if isinstance(row.get("date"), datetime):
                row["date"] = row["date"].date()
        st.session_state[pending_key] = rows

    # Ajout piloté par un bouton (pas le "+" natif, qui ajoute toujours en bas et
    # perturbe le suivi des lignes existantes) : la nouvelle ligne vide s'insère
    # en tête, remplie sur place, tri du plus récent au plus ancien respecté.
    if st.button("➕ Ajouter une transaction", key=f"{key}_add_row"):
        _carry_over_pending()
        blank_row = {"id": None, "date": date.today(), "label": "", "amount": 0.0, "category": None}
        if account_options:
            blank_row["compte"] = None
        st.session_state[pending_key].insert(0, blank_row)
        # Une nouvelle ligne en tête décale la position de toutes les lignes
        # existantes. Le data_editor mémorise ses modifications (dont les cases
        # "Supprimer" cochées) par position sous sa clé : sans ce changement de
        # version, ces marques se retrouveraient réappliquées aux mauvaises
        # lignes après le décalage (ex. une suppression en attente semble
        # "annulée" tandis qu'une autre ligne se coche à sa place).
        st.session_state[version_key] += 1

    display_cols = [c for c in ["id", "date", "label", "amount", "category"] if c in direction_df.columns]
    working = direction_df.select(display_cols).with_columns(pl.col("amount").abs())

    if account_options:
        id_to_account_name = {v: k for k, v in account_options.items()}
        account_ids = direction_df["account_id"].to_list() if "account_id" in direction_df.columns else []
        working = working.with_columns(
            pl.Series("compte", [id_to_account_name.get(a) for a in account_ids])
        )

    if st.session_state[pending_key]:
        pending_df = pl.DataFrame(st.session_state[pending_key], schema=working.schema)
        working = pl.concat([pending_df, working], how="diagonal_relaxed")

    working = working.with_columns(pl.lit(False).alias("Supprimer"))

    column_config: dict = {
        "id": None,
        "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
        "label": st.column_config.TextColumn("Libellé", width="large"),
        "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €", min_value=0.0),
        "category": st.column_config.SelectboxColumn("Catégorie", options=categories, required=False),
        "Supprimer": st.column_config.CheckboxColumn("🗑️ Supprimer"),
    }
    if account_options:
        column_config["compte"] = st.column_config.SelectboxColumn(
            "Compte", options=list(account_options.keys()), required=False
        )

    edited = st.data_editor(
        working,
        key=f"{key}_editor_v{st.session_state[version_key]}",
        width='stretch',
        hide_index=True,
        num_rows="fixed",
        disabled=["id"],
        column_config=column_config,
    )
    if not isinstance(edited, pl.DataFrame):
        edited = pl.from_pandas(edited)
    st.session_state[last_edited_key] = edited

    # La suppression n'a lieu que si la case ET le bouton sont utilisés — pas la
    # case seule — pour éviter une suppression accidentelle en un clic. Elle est
    # immédiate (pas différée jusqu'à "Enregistrer") pour ne pas dépendre du
    # suivi par position du data_editor, fragile dès que les lignes bougent
    # (ex. ajout d'une nouvelle ligne) pour une action destructive.
    #
    # Une ligne en attente (pas encore enregistrée) cochée "Supprimer" est comptée
    # à part : rien à supprimer en base pour elle (delete_transaction a besoin d'un
    # id réel), _carry_over_pending() l'écarte simplement au clic. Sans ce second
    # compteur, cocher une ligne tout juste ajoutée laissait le bouton grisé sur
    # "(0)" — impossible de la retirer autrement qu'en vidant tous ses champs.
    to_delete_now = [
        row["id"] for row in edited.iter_rows(named=True)
        if row.get("id") and row.get("Supprimer")
    ]
    to_discard_pending = [
        row for row in edited.iter_rows(named=True)
        if not row.get("id") and row.get("Supprimer")
    ]
    total_marked = len(to_delete_now) + len(to_discard_pending)
    if st.button(
        f"🗑️ Supprimer ({total_marked})",
        key=f"{key}_confirm_delete",
        disabled=not total_marked,
        width='stretch',
    ):
        try:
            _carry_over_pending()
            snapshot = direction_df.filter(pl.col("id").is_in(to_delete_now)).to_dicts()
            for row_id in to_delete_now:
                delete_transaction(row_id)
            st.session_state[undo_key] = snapshot
            invalidate_cache()
            del st.session_state[origin_key]
            st.session_state[version_key] += 1
            if to_delete_now and to_discard_pending:
                msg = (
                    f"{len(to_delete_now)} transaction(s) supprimée(s), "
                    f"{len(to_discard_pending)} ligne(s) en attente écartée(s) 🗑️"
                )
            elif to_discard_pending:
                msg = f"{len(to_discard_pending)} ligne(s) en attente écartée(s) 🗑️"
            else:
                msg = f"{len(to_delete_now)} transaction(s) supprimée(s) ✅"
            st.toast(msg, icon="🗑️")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de la suppression : {exc}")
        return

    # Le bouton "Annuler" ne s'affiche que juste après une suppression, tant
    # qu'elle n'a pas été remplacée par une autre — pas de bouton grisé en
    # permanence.
    if st.session_state[undo_key]:
        if st.button(
            f"↩️ Annuler la dernière suppression ({len(st.session_state[undo_key])})",
            key=f"{key}_undo_delete",
            width='stretch',
        ):
            try:
                _carry_over_pending()
                for row in st.session_state[undo_key]:
                    restore_payload = {
                        k: v for k, v in row.items() if k not in ("id", "created_at", "is_income")
                    }
                    # Le snapshot vient directement de Polars : "date" y est un objet
                    # datetime.date, pas un texte. Le client Supabase sérialise le payload
                    # en JSON, qui ne sait pas encoder un date brut (TypeError) — d'où
                    # l'échec systématique de la restauration sans ça.
                    row_date = restore_payload.get("date")
                    if hasattr(row_date, "isoformat"):
                        restore_payload["date"] = row_date.isoformat()
                    insert_transaction(restore_payload)
                restored_count = len(st.session_state[undo_key])
                st.session_state[undo_key] = []
                invalidate_cache()
                del st.session_state[origin_key]
                st.session_state[version_key] += 1
                st.toast(f"{restored_count} transaction(s) restaurée(s) ✅", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur lors de la restauration : {exc}")
            return

    # Un bouton explicite (pas de sauvegarde à chaque frappe) : Streamlit relance
    # toute la page à chaque édition de cellule, et un appel réseau Supabase à
    # chaque frappe ralentissait tout et pouvait se faire doubler par la frappe
    # suivante avant d'avoir fini (écran incohérent, pertes de saisie). Un seul
    # appel groupé au clic est plus rapide et plus fiable.
    if not st.button("💾 Enregistrer", key=f"{key}_save", width='stretch'):
        return

    origin_map = {row["id"]: row for row in st.session_state[origin_key] if row.get("id")}
    sign = 1.0 if direction == "income" else -1.0

    new_rows: list[dict] = []
    updates: list[tuple[str, dict]] = []
    incomplete_rows: list[dict] = []

    for row in edited.iter_rows(named=True):
        row_id = row.get("id")
        row_date = row.get("date")
        row_date_iso = row_date.isoformat() if hasattr(row_date, "isoformat") else row_date

        if row_id is None:
            # Nouvelle ligne (ajoutée via le bouton "➕") — jamais enregistrée si
            # l'utilisateur vient de la cocher pour suppression.
            if row.get("Supprimer"):
                continue
            if not row.get("label") or not row_date_iso or not row.get("amount"):
                # Incomplète : gardée en attente (jamais effacée en silence),
                # avec un message expliquant ce qu'il manque.
                has_content = bool((row.get("label") or "").strip()) or bool(row.get("amount")) or row.get("category")
                if has_content:
                    kept = {k: v for k, v in row.items() if k != "Supprimer"}
                    if isinstance(kept.get("date"), datetime):
                        kept["date"] = kept["date"].date()
                    incomplete_rows.append(kept)
                continue
            acc = account_options.get(row.get("compte")) if account_options else account_id
            new_rows.append({
                "date": row_date_iso,
                "amount": abs(float(row["amount"])) * sign,
                "label": row["label"],
                "source": str(TransactionSource.MANUAL),
                "business_id": business_id,
                "account_id": acc,
                "category": row.get("category"),
                "notes": None,
            })
        else:
            orig = origin_map.get(row_id, {})
            diff: dict = {}
            if row.get("label") != orig.get("label"):
                diff["label"] = row.get("label")
            if row.get("category") != orig.get("category"):
                diff["category"] = row.get("category")
            new_amount = abs(float(row["amount"])) * sign
            if abs(new_amount - float(orig.get("amount", 0) or 0)) > 0.001:
                diff["amount"] = new_amount
            if str(row_date_iso) != str(orig.get("date")):
                diff["date"] = row_date_iso
            if account_options:
                new_acc = account_options.get(row.get("compte"))
                if new_acc != orig.get("account_id"):
                    diff["account_id"] = new_acc
            if diff:
                updates.append((row_id, diff))

    if not new_rows and not updates:
        # Rien de complet à enregistrer (ligne(s) incomplète(s) et/ou aucune
        # modification) : on prévient plutôt que de faire disparaître la saisie.
        st.session_state[pending_key] = incomplete_rows
        if incomplete_rows:
            st.warning(
                f"{len(incomplete_rows)} ligne(s) incomplète(s) — "
                "libellé, date et montant sont obligatoires."
            )
        return

    # Chaque insert/update est isolé dans son propre try/except : un échec réseau
    # ponctuel sur une ligne (ex. hoquet de connexion à Supabase) ne doit jamais
    # faire échouer silencieusement les autres lignes déjà persistées avant elle
    # — sans quoi la ligne était bel et bien enregistrée en base, mais l'écran
    # restait figé sur l'ancien état (pas de refresh), donnant l'impression
    # qu'elle avait disparu et poussant à la ressaisir en double.
    inserted, updated, errors = 0, 0, []
    for payload in new_rows:
        try:
            insert_transaction(payload)
            inserted += 1
        except Exception as exc:
            errors.append(f"« {payload['label']} » ({payload['date']}) : {exc}")
    for row_id, diff in updates:
        try:
            update_transaction(row_id, diff)
            updated += 1
        except Exception as exc:
            errors.append(f"Modification {row_id} : {exc}")

    if inserted or updated:
        invalidate_cache()
        del st.session_state[origin_key]
        st.session_state[pending_key] = incomplete_rows
        st.session_state[version_key] += 1
        if errors:
            st.toast(
                f"{inserted} ajoutée(s), {updated} modifiée(s) — "
                f"{len(errors)} échec(s), voir ci-dessous ⚠️",
                icon="⚠️",
            )
        else:
            st.toast(f"{inserted} ajoutée(s), {updated} modifiée(s) ✅", icon="✅")
        st.rerun()
    else:
        st.session_state[pending_key] = incomplete_rows

    if errors:
        st.error("Échec de l'enregistrement :\n" + "\n".join(f"- {e}" for e in errors))
