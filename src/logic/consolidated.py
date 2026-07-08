"""Agrégations transversales : flux par compte réel, appariement des virements."""

import polars as pl


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
