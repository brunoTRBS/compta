"""Tests du tri des opérations du compte commun (libellés tirés d'un vrai relevé)."""

from src.config import PARTICIPATION_CATEGORY
from src.logic.household import (
    KIND_CARD,
    KIND_PARTICIPATION,
    classify_joint_transactions,
    participation_expense,
    review_kind,
)


def _tx(label, amount, id_="t1", ext="cm_abc"):
    return {"id": id_, "date": "2026-10-08", "amount": amount, "label": label,
            "raw_label": label, "account_id": "acc-commun", "external_id": ext}


OWN_CARD = _tx("PAIEMENT PSC 0910 BEYNOST E LECLERC CARTE 3935 HIR012628507447803", -43.06)
OTHER_CARD = _tx("PAIEMENT CB 0610 BEYNOST E LECLERC CARTE 1295 HIR012628004430068", -27.97)
PARTICIPATION = _tx("VIR INST MME CHARLOTTE PARIS LOYER 6281172804484747", 950.0)
REJECTED = _tx("REJ VIR INST CHARLOTTE PARIS CH3W26266M034811", 698.0)
OUTGOING_TO_HER = _tx("VIR INST CHARLOTTE PARIS CH3W26266M034811", -698.0)
SALARY = _tx("DATALYO SALAIRE 09/2026 DATALYO", 2614.12)
DIRECT_DEBIT = _tx("PRLV SEPA MATMUT ROUEN 2026100500009840010002361", -73.19)


class TestReviewKind:
    def test_own_card(self):
        assert review_kind(OWN_CARD) == KIND_CARD

    def test_other_card_needs_no_review(self):
        assert review_kind(OTHER_CARD) is None

    def test_card_number_must_match_exactly(self):
        assert review_kind(_tx("PAIEMENT CB LYON CARTE 39351 HIR0", -1.0)) is None

    def test_transfer_from_her_is_participation(self):
        assert review_kind(PARTICIPATION) == KIND_PARTICIPATION

    def test_reversed_name_order(self):
        assert review_kind(_tx("VIR INST PARIS CHARLOTTE", 950.0)) == KIND_PARTICIPATION

    def test_rejected_transfer_is_not_participation(self):
        assert review_kind(REJECTED) is None

    def test_outgoing_transfer_to_her_is_not_participation(self):
        assert review_kind(OUTGOING_TO_HER) is None

    def test_household_operations_need_no_review(self):
        assert review_kind(SALARY) is None
        assert review_kind(DIRECT_DEBIT) is None


def test_classify_marks_everything_household():
    result = classify_joint_transactions([OWN_CARD, OTHER_CARD, PARTICIPATION, SALARY])
    assert all(r["business_id"] == "household" for r in result)
    assert [r["needs_review"] for r in result] == [True, False, True, False]


def test_participation_expense():
    exp = participation_expense(PARTICIPATION)
    assert exp["amount"] == -950.0
    assert exp["category"] == PARTICIPATION_CATEGORY
    assert exp["business_id"] == "personal"
    assert exp["business_id"] == "personal"
    assert exp["external_id"] == "cm_abc_part"


def test_is_household():
    from src.logic.household import is_household

    assert is_household({"business_id": "household"})
    assert not is_household({"business_id": "personal"})
    assert not is_household({})


def test_default_business_id_joint_account_is_household():
    from src.logic.household import default_business_id

    assert default_business_id({"name": "Compte commun", "owner": "personal"}) == "household"
    assert default_business_id({"name": "Compte perso", "owner": "personal"}) == "personal"
    assert default_business_id({"name": "Compte pro coaching", "owner": "phi_rising"}) == "phi_rising"
