"""Agrégations transversales : flux par compte réel, appariement des virements."""

import polars as pl

_PERSONAL_INCOME_SCHEMA = {
    "date": pl.Date,
    "label": pl.Utf8,
    "amount": pl.Float64,
    "transfer_group_id": pl.Utf8,
    "year": pl.Int32,
    "month_num": pl.Int32,
}


def flows_per_account(tx_df: pl.DataFrame, accounts_df: pl.DataFrame) -> pl.DataFrame:
    """Solde courant + flux de la période pour chaque compte réel.

    Args:
        tx_df: transactions de la période, virements inclus (include_transfers=True) —
            un virement déplace réellement de l'argent d'un compte à l'autre.
        accounts_df: comptes actifs (colonnes id, name, institution, type, owner, balance...).

    Returns:
        accounts_df enrichi d'une colonne "flux" (Float64, 0.0 si aucun mouvement).
    """
    if accounts_df.is_empty():
        return accounts_df

    if tx_df.is_empty() or "account_id" not in tx_df.columns:
        flows = pl.DataFrame(schema={"account_id": pl.Utf8, "flux": pl.Float64})
    else:
        flows = (
            tx_df.filter(pl.col("account_id").is_not_null())
            .group_by("account_id")
            .agg(pl.col("amount").sum().alias("flux"))
        )

    return (
        accounts_df.join(flows, left_on="id", right_on="account_id", how="left")
        .with_columns(pl.col("flux").fill_null(0.0))
    )


def pair_transfers(tx_df: pl.DataFrame, accounts_df: pl.DataFrame) -> pl.DataFrame:
    """Reconstitue chaque virement à partir de ses 2 écritures liées.

    Args:
        tx_df: transactions de la période, virements inclus (is_transfer=true attendu
            pour les lignes concernées ; les autres sont ignorées).
        accounts_df: comptes actifs, pour résoudre account_id → nom lisible.

    Returns:
        Un DataFrame : transfer_group_id, date, label, from_account, to_account, amount
        (positif). transfer_group_id est conservé pour permettre la suppression du
        virement (les 2 écritures partagent le même). Vide si aucun virement sur la période.
    """
    transfers = tx_df.filter(pl.col("is_transfer"))
    if transfers.is_empty():
        return pl.DataFrame()

    from_legs = (
        transfers.filter(pl.col("amount") < 0)
        .select(["transfer_group_id", "date", "label", "amount", "account_id"])
        .rename({"account_id": "from_account_id", "amount": "from_amount"})
    )
    to_legs = (
        transfers.filter(pl.col("amount") > 0)
        .select(["transfer_group_id", "account_id"])
        .rename({"account_id": "to_account_id"})
    )

    paired = from_legs.join(to_legs, on="transfer_group_id", how="inner").with_columns(
        pl.col("from_amount").abs().alias("amount")
    ).drop("from_amount")

    if paired.is_empty():
        return paired

    names = accounts_df.select(["id", "name"]) if not accounts_df.is_empty() else pl.DataFrame(
        schema={"id": pl.Utf8, "name": pl.Utf8}
    )
    paired = (
        paired
        .join(names.rename({"id": "from_account_id", "name": "from_account"}), on="from_account_id", how="left")
        .join(names.rename({"id": "to_account_id", "name": "to_account"}), on="to_account_id", how="left")
    )

    return paired.select(
        ["transfer_group_id", "date", "label", "from_account", "to_account", "amount"]
    ).sort("date", descending=True)


def personal_income_from_transfers(tx_df: pl.DataFrame, accounts_df: pl.DataFrame) -> pl.DataFrame:
    """Virements à traiter comme un revenu personnel plutôt qu'un simple mouvement interne.

    Concerne les virements dont la destination est un compte Perso et la source est soit
    Booth in Lyon (l'argent devient alors réellement disponible), soit n'importe quel
    compte d'épargne (on "désépargne"). Les virements depuis Phi Rising sont exclus : son
    bénéfice est déjà compté comme revenu perso ailleurs (voir revenue.monthly_benefice),
    l'ajouter ici ferait doublon. Les mouvements purement internes au perso (compte courant
    vers compte courant) restent de simples virements, jamais un revenu.

    Args:
        tx_df: transactions, virements inclus (include_transfers=True).
        accounts_df: comptes actifs (colonnes id, owner, type).

    Returns:
        DataFrame : date, label, amount (positif), transfer_group_id, year, month_num.
        Vide si aucun virement éligible.
    """
    if tx_df.is_empty() or accounts_df.is_empty():
        return pl.DataFrame(schema=_PERSONAL_INCOME_SCHEMA)

    transfers = tx_df.filter(pl.col("is_transfer"))
    if transfers.is_empty():
        return pl.DataFrame(schema=_PERSONAL_INCOME_SCHEMA)

    to_legs = (
        transfers.filter(pl.col("amount") > 0)
        .join(
            accounts_df.select(["id", "owner"]).rename({"id": "account_id", "owner": "to_owner"}),
            on="account_id", how="left",
        )
        .filter(pl.col("to_owner") == "personal")
    )
    from_legs = (
        transfers.filter(pl.col("amount") < 0)
        .join(
            accounts_df.select(["id", "owner", "type"]).rename(
                {"id": "account_id", "owner": "from_owner", "type": "from_type"}
            ),
            on="account_id", how="left",
        )
        .select(["transfer_group_id", "from_owner", "from_type"])
    )

    eligible = (
        to_legs.join(from_legs, on="transfer_group_id", how="left")
        .filter((pl.col("from_owner") == "booth_in_lyon") | (pl.col("from_type") == "savings"))
    )

    if eligible.is_empty():
        return pl.DataFrame(schema=_PERSONAL_INCOME_SCHEMA)

    return eligible.select(["date", "label", "amount", "transfer_group_id"]).with_columns(
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month_num"),
    )
