import pytest
from decimal import Decimal

from src.config import BusinessId, CA_THRESHOLDS, URSSAF_RATES
from src.logic.urssaf import UrssafResult, compute_cotisations, compute_quarterly_estimate


class TestComputeCotisations:
    def test_normal_case_phi_rising(self):
        result = compute_cotisations(Decimal("10000"), BusinessId.PHI_RISING)
        expected = (Decimal("10000") * URSSAF_RATES[BusinessId.PHI_RISING]).quantize(Decimal("0.01"))
        assert result.cotisations == expected
        assert result.ca == Decimal("10000")
        assert not result.is_above_threshold

    def test_normal_case_booth_in_lyon(self):
        result = compute_cotisations(Decimal("5000"), BusinessId.BOOTH_IN_LYON)
        expected = (Decimal("5000") * URSSAF_RATES[BusinessId.BOOTH_IN_LYON]).quantize(Decimal("0.01"))
        assert result.cotisations == expected

    def test_zero_ca(self):
        result = compute_cotisations(Decimal("0"), BusinessId.PHI_RISING)
        assert result.cotisations == Decimal("0.00")
        assert result.total_charges == Decimal("0.00")
        assert not result.is_above_threshold

    def test_above_threshold_triggers_flag(self):
        threshold = CA_THRESHOLDS[BusinessId.PHI_RISING]
        ca_above = threshold + Decimal("1000")
        result = compute_cotisations(ca_above, BusinessId.PHI_RISING)
        assert result.is_above_threshold

    def test_cotisations_not_capped_above_threshold(self):
        # Les cotisations sont calculées sur le CA total, même au-dessus du seuil
        threshold = CA_THRESHOLDS[BusinessId.PHI_RISING]
        ca_above = threshold + Decimal("1000")
        result = compute_cotisations(ca_above, BusinessId.PHI_RISING)
        expected = (ca_above * URSSAF_RATES[BusinessId.PHI_RISING]).quantize(Decimal("0.01"))
        assert result.cotisations == expected

    def test_exactly_at_threshold_not_above(self):
        threshold = CA_THRESHOLDS[BusinessId.PHI_RISING]
        result = compute_cotisations(threshold, BusinessId.PHI_RISING)
        assert not result.is_above_threshold

    def test_versement_liberatoire_included(self):
        result = compute_cotisations(
            Decimal("10000"),
            BusinessId.PHI_RISING,
            with_versement_liberatoire=True,
        )
        assert result.versement_liberatoire > Decimal("0")
        assert result.total_charges == result.cotisations + result.versement_liberatoire

    def test_versement_liberatoire_excluded_by_default(self):
        result = compute_cotisations(Decimal("10000"), BusinessId.PHI_RISING)
        assert result.versement_liberatoire == Decimal("0.00")
        assert result.total_charges == result.cotisations

    def test_negative_ca_raises(self):
        with pytest.raises(ValueError, match="négatif"):
            compute_cotisations(Decimal("-100"), BusinessId.PHI_RISING)

    def test_returns_named_tuple(self):
        result = compute_cotisations(Decimal("5000"), BusinessId.PHI_RISING)
        assert isinstance(result, UrssafResult)

    def test_rounding_half_up(self):
        # 10001 * 0.212 = 2120.212 → arrondi à 2120.21
        result = compute_cotisations(Decimal("10001"), BusinessId.PHI_RISING)
        assert result.cotisations == Decimal("2120.21")

    def test_ca_threshold_present_in_result(self):
        threshold = CA_THRESHOLDS[BusinessId.PHI_RISING]
        result = compute_cotisations(Decimal("5000"), BusinessId.PHI_RISING)
        assert result.ca_threshold == threshold


class TestComputeQuarterlyEstimate:
    def test_normal_quarter(self):
        revenues = [Decimal("3000"), Decimal("4000"), Decimal("3500")]
        result = compute_quarterly_estimate(revenues, BusinessId.PHI_RISING, quarter=1)
        assert result.ca == Decimal("10500")
        expected = (Decimal("10500") * URSSAF_RATES[BusinessId.PHI_RISING]).quantize(Decimal("0.01"))
        assert result.cotisations == expected

    def test_wrong_number_of_months_raises(self):
        with pytest.raises(ValueError, match="3 mois"):
            compute_quarterly_estimate(
                [Decimal("1000"), Decimal("2000")], BusinessId.PHI_RISING, quarter=1
            )

    def test_invalid_quarter_raises(self):
        revenues = [Decimal("1000")] * 3
        with pytest.raises(ValueError, match="trimestre"):
            compute_quarterly_estimate(revenues, BusinessId.PHI_RISING, quarter=5)

    def test_zero_quarter(self):
        result = compute_quarterly_estimate(
            [Decimal("0"), Decimal("0"), Decimal("0")], BusinessId.PHI_RISING, quarter=2
        )
        assert result.cotisations == Decimal("0.00")
        assert not result.is_above_threshold

    def test_all_quarters_valid(self):
        revenues = [Decimal("2000")] * 3
        for q in range(1, 5):
            result = compute_quarterly_estimate(revenues, BusinessId.PHI_RISING, quarter=q)
            assert result.ca == Decimal("6000")
