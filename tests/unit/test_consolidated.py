import polars as pl
import pytest
from datetime import date

from src.logic.consolidated import flows_per_account, pair_transfers


@pytest.fixture
def sample_accounts():
    return pl.DataFrame({
        "id": ["acc-coaching", "acc-photobooth", "acc-perso", "acc-commun", "acc-livret"],
        "name": ["Compte pro coaching", "Compte pro photobooth", "Compte perso", "Compte commun", "Livret épargne"],
        "institution": ["Hello Bank", "Revolut", "Boursobank", "Hello Bank", "Boursobank"],
        "type": ["current", "revolut", "current", "current", "savings"],
        "owner": ["phi_rising", "booth_in_lyon", "personal", "personal", "personal"],
        "balance": pl.Series([1000.0, 500.0, 2000.0, 800.0, 5000.0], dtype=pl.Float64),
    })


@pytest.fixture
def sample_transactions():
    return pl.DataFrame({
        "transfer_group_id": ["tg-1", "tg-1", None, None],
        "date": pl.Series(
            [date(2024, 6, 1), date(2024, 6, 1), date(2024, 6, 5), date(2024, 6, 10)],
            dtype=pl.Date,
        ),
        "label": ["Retrait Booth vers perso", "Retrait Booth vers perso", "Coaching client", "Courses"],
        "amount": pl.Series([-200.0, 200.0, 300.0, -50.0], dtype=pl.Float64),
        "account_id": ["acc-photobooth", "acc-perso", "acc-coaching", "acc-perso"],
        "is_transfer": [True, True, False, False],
    })


class TestFlowsPerAccount:
    def test_all_accounts_present_even_without_movement(self, sample_accounts, sample_transactions):
        result = flows_per_account(sample_transactions, sample_accounts)
        assert result.shape[0] == 5
        commun = result.filter(pl.col("id") == "acc-commun")
        assert commun["flux"][0] == pytest.approx(0.0)

    def test_flux_sums_all_movements_including_transfers(self, sample_accounts, sample_transactions):
        result = flows_per_account(sample_transactions, sample_accounts)
        perso = result.filter(pl.col("id") == "acc-perso")
        # +200 (virement reçu) - 50 (courses) = 150
        assert perso["flux"][0] == pytest.approx(150.0)

    def test_photobooth_flux_is_negative(self, sample_accounts, sample_transactions):
        result = flows_per_account(sample_transactions, sample_accounts)
        photobooth = result.filter(pl.col("id") == "acc-photobooth")
        assert photobooth["flux"][0] == pytest.approx(-200.0)

    def test_empty_transactions_returns_zero_flux(self, sample_accounts):
        empty = pl.DataFrame(schema={"account_id": pl.Utf8, "amount": pl.Float64})
        result = flows_per_account(empty, sample_accounts)
        assert result["flux"].to_list() == [0.0] * 5

    def test_empty_accounts_returns_empty(self, sample_transactions):
        empty = pl.DataFrame(schema={"id": pl.Utf8, "name": pl.Utf8})
        result = flows_per_account(sample_transactions, empty)
        assert result.is_empty()


class TestPairTransfers:
    def test_pairs_the_two_legs_into_one_row(self, sample_accounts, sample_transactions):
        result = pair_transfers(sample_transactions, sample_accounts)
        assert result.shape[0] == 1

    def test_keeps_transfer_group_id_for_deletion(self, sample_accounts, sample_transactions):
        result = pair_transfers(sample_transactions, sample_accounts)
        assert result["transfer_group_id"][0] == "tg-1"

    def test_resolves_account_names(self, sample_accounts, sample_transactions):
        result = pair_transfers(sample_transactions, sample_accounts)
        row = result.row(0, named=True)
        assert row["from_account"] == "Compte pro photobooth"
        assert row["to_account"] == "Compte perso"

    def test_amount_is_positive(self, sample_accounts, sample_transactions):
        result = pair_transfers(sample_transactions, sample_accounts)
        assert result["amount"][0] == pytest.approx(200.0)

    def test_non_transfer_rows_ignored(self, sample_accounts, sample_transactions):
        result = pair_transfers(sample_transactions, sample_accounts)
        # Coaching client / Courses ne sont pas des virements → 1 seule ligne au total
        assert result.shape[0] == 1

    def test_no_transfers_returns_empty(self, sample_accounts):
        no_transfers = pl.DataFrame({
            "transfer_group_id": [None],
            "date": pl.Series([date(2024, 6, 1)], dtype=pl.Date),
            "label": ["Coaching"],
            "amount": pl.Series([300.0], dtype=pl.Float64),
            "account_id": ["acc-coaching"],
            "is_transfer": [False],
        })
        result = pair_transfers(no_transfers, sample_accounts)
        assert result.is_empty()
