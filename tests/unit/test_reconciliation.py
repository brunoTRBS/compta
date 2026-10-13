"""Tests du contrôle de solde."""

from datetime import date

import polars as pl

from src.logic.reconciliation import account_status, check_account, statement_closing_balance


def test_closing_balance_credit_mutuel_last_row_of_last_day():
    rows = [
        {"date": "2026-10-12", "balance": 6434.10},
        {"date": "2026-10-12", "balance": 6431.50},
        {"date": "2026-10-08", "balance": 4853.38},
    ]
    assert statement_closing_balance(rows) == ("2026-10-12", 6431.50)


def test_closing_balance_none_without_balance():
    assert statement_closing_balance([{"date": "2026-10-12", "balance": None}]) is None


def _snaps(*pairs):
    return pl.DataFrame({"date": [date.fromisoformat(d) for d, _ in pairs],
                         "balance": [b for _, b in pairs]})


def _txs(*rows):
    return pl.DataFrame({
        "date": [date.fromisoformat(d) for d, _, _ in rows],
        "amount": [a for _, a, _ in rows],
        "external_id": [e for _, _, e in rows],
    }, schema_overrides={"external_id": pl.Utf8})


def test_complete_account():
    periods = check_account(
        _snaps(("2026-10-05", 168.71), ("2026-10-12", 0.96)),
        _txs(("2026-10-12", -164.75, "a"), ("2026-10-12", -3.0, "b")),
    )
    assert account_status(periods) == (True, 0.0)


def test_missing_operation_shows_gap():
    periods = check_account(
        _snaps(("2026-10-05", 168.71), ("2026-10-12", 0.96)),
        _txs(("2026-10-12", -164.75, "a")),
    )
    complete, gap = account_status(periods)
    assert complete is False
    assert gap == -3.0


def test_operations_on_start_date_not_counted():
    """Le solde de départ inclut déjà les opérations de ce jour-là."""
    periods = check_account(
        _snaps(("2026-10-05", 100.0), ("2026-10-12", 100.0)),
        _txs(("2026-10-05", -50.0, "a")),
    )
    assert account_status(periods)[0] is True


def test_participation_lines_ignored():
    periods = check_account(
        _snaps(("2026-10-01", 0.0), ("2026-10-12", 950.0)),
        _txs(("2026-10-08", 950.0, "cm_x"), ("2026-10-08", -950.0, "cm_x_part")),
    )
    assert account_status(periods)[0] is True


def test_single_snapshot_no_check():
    assert check_account(_snaps(("2026-10-12", 1.0)), _txs()) == []
