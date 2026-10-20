"""Tests du simulateur de budget pro."""

from datetime import date

import polars as pl
import pytest

from src.config import BusinessId
from src.logic.simulator import (
    average_monthly_expenses,
    categories_for,
    month_label,
    month_options,
    simulate,
    simulate_month,
)


def test_categories_follow_each_activity():
    assert categories_for(BusinessId.PHI_RISING) == ["BNC", "BIC", "ND"]
    assert "Évenement Privé" in categories_for(BusinessId.BOOTH_IN_LYON)


def test_month_options_cross_new_year():
    options = month_options(date(2026, 11, 15), count=3)
    assert options == ["2026-11", "2026-12", "2027-01"]
    assert month_label("2027-01") == "Jan 2027"


def test_month_applies_category_rate():
    result = simulate_month(
        [{"category": "BNC", "amount": 1000.0}], charges=100.0,
        business_id=BusinessId.PHI_RISING, month="2026-11",
    )
    assert result["ca"] == 1000.0
    assert result["urssaf"] == 280.0           # 28 % de BNC
    assert result["remaining"] == pytest.approx(1000 - 280 - 100)


def test_stripe_fees_reduce_urssaf_base_and_remaining():
    result = simulate_month(
        [{"category": "BNC", "amount": 1000.0, "fees": 30.0}], charges=0.0,
        business_id=BusinessId.PHI_RISING, month="2026-11",
    )
    assert result["urssaf"] == pytest.approx(271.6)   # (1000 − 30) × 28 %
    assert result["remaining"] == pytest.approx(1000 - 30 - 271.6)


def test_non_declared_income_is_not_taxed():
    result = simulate_month(
        [{"category": "ND", "amount": 200.0}], charges=0.0,
        business_id=BusinessId.PHI_RISING, month="2026-11",
    )
    assert result["urssaf"] == 0.0
    assert result["remaining"] == 200.0


def test_versement_liberatoire_is_optional():
    without = simulate_month([{"category": "BNC", "amount": 1000.0}], 0, BusinessId.PHI_RISING, "2026-11")
    with_vl = simulate_month([{"category": "BNC", "amount": 1000.0}], 0, BusinessId.PHI_RISING, "2026-11", True)
    assert with_vl["urssaf"] == pytest.approx(without["urssaf"] + 22.0)  # 2,2 %


def test_simulate_groups_months_in_order_and_totals():
    result = simulate(
        [
            {"month": "2026-12", "category": "BNC", "amount": 500.0},
            {"month": "2026-11", "category": "BNC", "amount": 1000.0},
            {"month": "2026-11", "category": "BIC", "amount": 100.0},
            {"month": "2026-11", "category": "BNC", "amount": 0.0},     # ligne vide ignorée
            {"month": None, "category": "BNC", "amount": 999.0},        # sans mois : ignorée
        ],
        charges=50.0, business_id=BusinessId.PHI_RISING, year_to_date_ca=10_000.0,
    )
    assert [m["month"] for m in result["months"]] == ["2026-11", "2026-12"]
    assert result["months"][0]["urssaf"] == pytest.approx(1000 * 0.28 + 100 * 0.27)
    assert result["total"]["ca"] == 1600.0
    assert result["total"]["charges"] == 100.0       # 50 € par mois simulé
    assert result["ca_after"] == 11_600.0
    assert result["threshold"] > result["ca_after"]


def test_empty_simulation_is_empty():
    result = simulate([], 0.0, BusinessId.BOOTH_IN_LYON)
    assert result["months"] == []
    assert result["total"]["remaining"] == 0.0


def test_average_monthly_expenses_uses_last_complete_months():
    history = pl.DataFrame({
        "date": [date(2026, 7, 5), date(2026, 8, 5), date(2026, 9, 5), date(2026, 9, 6),
                 date(2026, 6, 5), date(2026, 10, 2)],
        "amount": [-30.0, -60.0, -90.0, -20.0, -999.0, -500.0],
        "category": ["Logiciels", "Logiciels", "Logiciels", "Stripe", "Logiciels", "Logiciels"],
        "is_transfer": [False, False, False, False, False, False],
    })
    # Juil + Août + Sept (hors Stripe) = 180 → 60 par mois ; juin trop ancien, octobre en cours
    assert average_monthly_expenses(history, date(2026, 10, 15), months=3) == 60.0
    assert average_monthly_expenses(pl.DataFrame(), date(2026, 10, 15)) == 0.0
