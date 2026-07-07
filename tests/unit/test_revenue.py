import polars as pl
import pytest

from src.config import BusinessId
from src.logic.revenue import aggregate_monthly, compute_net_margin, compute_ytd_summary


class TestAggregateMonthly:
    def test_returns_12_rows(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        assert len(result) == 12

    def test_january_revenue(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        jan = result.filter(pl.col("month") == 1)
        assert float(jan["revenue"][0]) == 1500.0

    def test_january_expenses(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        jan = result.filter(pl.col("month") == 1)
        assert float(jan["expenses"][0]) == 200.0

    def test_january_net(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        jan = result.filter(pl.col("month") == 1)
        assert float(jan["net"][0]) == pytest.approx(1300.0)

    def test_missing_months_are_zero(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        march = result.filter(pl.col("month") == 3)
        assert float(march["revenue"][0]) == 0.0
        assert float(march["expenses"][0]) == 0.0

    def test_wrong_year_returns_all_zeros(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2020)
        assert result["revenue"].sum() == 0.0

    def test_columns_present(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        assert set(result.columns) == {"month", "revenue", "expenses", "net"}

    def test_sorted_by_month(self, phi_rising_transactions):
        result = aggregate_monthly(phi_rising_transactions, year=2024)
        assert result["month"].to_list() == list(range(1, 13))


class TestComputeYtdSummary:
    def test_expected_keys(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        expected_keys = {
            "ca", "stripe_fees", "ca_for_urssaf", "expenses",
            "cotisations", "versement_liberatoire",
            "total_charges", "net_margin", "ca_threshold", "is_above_threshold",
        }
        assert set(summary.keys()) == expected_keys

    def test_ca_value(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        assert summary["ca"] == pytest.approx(1500.0)

    def test_expenses_value(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        assert summary["expenses"] == pytest.approx(200.0)

    def test_no_stripe_fees_when_absent(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        assert summary["stripe_fees"] == pytest.approx(0.0)
        assert summary["ca_for_urssaf"] == pytest.approx(1500.0)

    def test_stripe_fees_deducted_from_ca_for_urssaf(self):
        from datetime import date
        df = pl.DataFrame({
            "id": ["r1", "r2", "s1"],
            "date": pl.Series([date(2024, 1, 10), date(2024, 1, 20), date(2024, 1, 31)], dtype=pl.Date),
            "amount": pl.Series([1000.0, 500.0, -25.0], dtype=pl.Float64),
            "label": ["Coaching A", "Coaching B", "frais stripe"],
            "source": ["manual", "manual", "manual"],
            "business_id": ["phi_rising", "phi_rising", "phi_rising"],
            "category": ["BNC", "BNC", "Stripe"],
            "is_income": [True, True, False],
        })
        summary = compute_ytd_summary(df, BusinessId.PHI_RISING, year=2024)
        assert summary["ca"] == pytest.approx(1500.0)
        assert summary["stripe_fees"] == pytest.approx(25.0)
        assert summary["ca_for_urssaf"] == pytest.approx(1475.0)
        from decimal import Decimal
        from src.config import URSSAF_RATES
        expected_cotisations = float((Decimal("1475.0") * URSSAF_RATES[BusinessId.PHI_RISING]).quantize(Decimal("0.01")))
        assert summary["cotisations"] == pytest.approx(expected_cotisations)

    def test_not_above_threshold(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        assert not summary["is_above_threshold"]

    def test_net_margin_formula(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        expected = summary["ca"] - summary["expenses"] - summary["total_charges"]
        assert summary["net_margin"] == pytest.approx(expected)

    def test_cotisations_positive(self, phi_rising_transactions):
        summary = compute_ytd_summary(phi_rising_transactions, BusinessId.PHI_RISING, year=2024)
        assert summary["cotisations"] > 0

    def test_empty_dataframe_returns_zeros(self):
        import polars as pl
        from datetime import date

        empty_df = pl.DataFrame({
            "id": pl.Series([], dtype=pl.Utf8),
            "date": pl.Series([], dtype=pl.Date),
            "amount": pl.Series([], dtype=pl.Float64),
            "label": pl.Series([], dtype=pl.Utf8),
            "source": pl.Series([], dtype=pl.Utf8),
            "business_id": pl.Series([], dtype=pl.Utf8),
            "category": pl.Series([], dtype=pl.Utf8),
            "is_income": pl.Series([], dtype=pl.Boolean),
        })
        summary = compute_ytd_summary(empty_df, BusinessId.PHI_RISING, year=2024)
        assert summary["ca"] == 0.0
        assert summary["cotisations"] == 0.0


class TestComputeNetMargin:
    def test_positive_margin(self):
        assert compute_net_margin(10000.0, 2000.0, 1500.0) == pytest.approx(6500.0)

    def test_zero_margin(self):
        assert compute_net_margin(1000.0, 800.0, 200.0) == pytest.approx(0.0)

    def test_negative_margin(self):
        assert compute_net_margin(500.0, 300.0, 300.0) == pytest.approx(-100.0)
