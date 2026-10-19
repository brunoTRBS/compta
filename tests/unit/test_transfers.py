"""Tests de la détection des virements internes dans les relevés importés."""

from src.logic.transfers import (
    default_counterpart,
    detect_transfers,
    find_bank_transfer_pairs,
    find_rejected_pairs,
    is_transfer_like,
    resolve_transfer_review,
)

PERSO, LIVRET, PHI = "acc-perso", "acc-livret", "acc-phi"
ACCOUNTS = [
    {"id": PERSO, "name": "Compte perso", "owner": "personal", "type": "current"},
    {"id": LIVRET, "name": "Livret épargne", "owner": "personal", "type": "savings"},
    {"id": PHI, "name": "Compte pro coaching", "owner": "phi_rising", "type": "current"},
]


def _row(label, amount, account=PERSO, day=1, **extra):
    return {"date": f"2026-10-{day:02d}", "amount": amount, "label": label,
            "raw_label": label, "account_id": account, "business_id": "personal",
            "is_transfer": False, "needs_review": False, **extra}


class TestIsTransferLike:
    def test_transfer_with_her_name(self):
        assert is_transfer_like(_row("VIR INST PARIS CHARLOTTE", -10.0))

    def test_transfer_to_livret(self):
        assert is_transfer_like(_row("VIR VERS LIVRET BOURSO", -100.0))

    def test_card_payment_is_not(self):
        assert not is_transfer_like(_row("CARTE 02/10/26 MAISON GOTAI CB*1111", -13.0))

    def test_transfer_from_someone_else_is_not(self):
        assert not is_transfer_like(_row("VIR INST M OU MME TABERNERO RESTIT CAUTION", 1230.91))

    def test_household_row_is_never(self):
        assert not is_transfer_like(_row("VIR INST MME CHARLOTTE PARIS LOYER", 950.0, business_id="household"))


def test_rejected_transfer_pair():
    vir = _row("VIR INST CHARLOTTE PRO CH3W26266M034542", -697.47)
    rej = _row("REJ VIR INST CHARLOTTE PRO CH3W26266M034542", 697.47)
    other = _row("VIR INST CHARLOTTE PRO CH3W99999", -697.47)
    assert find_rejected_pairs([other, vir, rej]) == [(vir, rej)]


class TestBankTransferPairs:
    def test_perso_to_livret_paired(self):
        out = _row("VIR INST PARIS CHARLOTTE", -100.0, PERSO, day=1)
        inc = _row("VIR INST PARIS CHARLOTTE", 100.0, LIVRET, day=2)
        assert find_bank_transfer_pairs([out], [inc]) == [(out, inc)]

    def test_same_account_not_paired(self):
        out = _row("VIR INST PARIS CHARLOTTE", -100.0, PERSO)
        inc = _row("VIR INST PARIS CHARLOTTE", 100.0, PERSO)
        assert find_bank_transfer_pairs([out, inc], []) == []

    def test_too_far_apart_not_paired(self):
        out = _row("VIR INST PARIS CHARLOTTE", -100.0, PERSO, day=1)
        inc = _row("VIR INST PARIS CHARLOTTE", 100.0, LIVRET, day=9)
        assert find_bank_transfer_pairs([out], [inc]) == []

    def test_unrelated_transfers_same_amount_not_paired(self):
        out = _row("VIR SEPA ASHLER - MANSON", -2600.0, PERSO)
        inc = _row("VIR INST M OU MME TABERNERO", 2600.0, LIVRET)
        assert find_bank_transfer_pairs([out], [inc]) == []


class TestDetectTransfers:
    def test_pair_with_existing_row_updates_it(self):
        new = _row("VIR INST PARIS CHARLOTTE", 100.0, LIVRET)
        existing = _row("VIR INST PARIS CHARLOTTE", -100.0, PERSO, id="old-1")
        rows, updates, n_pairs = detect_transfers([new], [existing])
        assert n_pairs == 1
        assert rows[0]["is_transfer"] is True
        assert updates[0]["id"] == "old-1"
        assert updates[0]["transfer_group_id"] == rows[0]["transfer_group_id"]

    def test_unpaired_transfer_needs_review(self):
        """Virement reçu du compte pro (non importé) : à confirmer."""
        new = _row("VIR INST MME CHARLOTTE PARIS", 800.0, PERSO)
        rows, updates, n_pairs = detect_transfers([new], [])
        assert n_pairs == 0 and updates == []
        assert rows[0]["needs_review"] is True
        assert rows[0]["is_transfer"] is False

    def test_regular_expense_untouched(self):
        new = _row("CARTE 01/10/26 DELIVEROO CB*1111", -14.95)
        rows, _, _ = detect_transfers([new], [])
        assert rows[0]["needs_review"] is False and rows[0]["is_transfer"] is False


class TestDefaultCounterpart:
    def test_outgoing_defaults_to_savings(self):
        assert default_counterpart(_row("VIR X", -10.0), ACCOUNTS)["id"] == LIVRET

    def test_incoming_defaults_to_phi_rising(self):
        assert default_counterpart(_row("VIR X", 800.0), ACCOUNTS)["id"] == PHI


class TestResolveTransferReview:
    def test_counterpart_creates_linked_leg(self):
        tx = _row("VIR INST MME CHARLOTTE PARIS", 800.0, PERSO, id="t1")
        updates, legs = resolve_transfer_review([tx], {"t1": ACCOUNTS[2]})
        assert updates[0]["is_transfer"] is True
        assert legs[0]["amount"] == -800.0
        assert legs[0]["account_id"] == PHI
        assert legs[0]["business_id"] == "phi_rising"
        assert legs[0]["transfer_group_id"] == updates[0]["transfer_group_id"]
        assert legs[0]["source"] == "manual"

    def test_not_a_transfer_only_clears_review(self):
        tx = _row("VIR INST PARIS CHARLOTTE", -10.0, PERSO, id="t1")
        updates, legs = resolve_transfer_review([tx], {"t1": None})
        assert updates == [{"id": "t1", "needs_review": False}]
        assert legs == []

    def test_same_account_is_not_a_transfer(self):
        tx = _row("VIR INST PARIS CHARLOTTE", -10.0, PERSO, id="t1")
        _, legs = resolve_transfer_review([tx], {"t1": ACCOUNTS[0]})
        assert legs == []


def test_second_leg_of_a_transfer_to_the_joint_account_is_household():
    tx = _row("VIR X", -100.0, PERSO, id="t1")
    joint = {"id": "acc-commun", "name": "Compte commun", "owner": "personal"}
    _, legs = resolve_transfer_review([tx], {"t1": joint})
    assert legs[0]["business_id"] == "household"
