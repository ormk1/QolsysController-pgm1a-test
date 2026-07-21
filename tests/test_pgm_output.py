"""Tests for QolsysPgmOutput model — identity, raw state, update, and isolation."""

from __future__ import annotations

from unittest.mock import MagicMock

from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.pgm_output import QolsysPgmOutput


# Synthetic fixture based on observed IQ4 PGM fields.
def _make_pgm(data: dict[str, str] | None = None) -> QolsysPgmOutput:
    defaults: dict[str, str] = {
        "partition_id": "0",
        "pgm_number": "0",
        "name": "Water Valve",
        "state": "0",
        "zoneID": "11",
    }
    if data:
        defaults.update(data)
    return QolsysPgmOutput(defaults)


class TestPgmIdentity:
    def test_stable_id_tuple(self) -> None:
        pgm = _make_pgm()
        assert pgm.stable_id == ("0", "0")

    def test_stable_id_different_partition(self) -> None:
        pgm = _make_pgm({"partition_id": "1", "pgm_number": "2"})
        assert pgm.stable_id == ("1", "2")

    def test_has_valid_identity_ok(self) -> None:
        pgm = _make_pgm()
        assert pgm.has_valid_identity() is True

    def test_has_valid_identity_missing_partition_id(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"pgm_number": "0", "name": "X", "state": "0"})
        assert pgm.has_valid_identity() is False

    def test_has_valid_identity_missing_pgm_number(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "name": "X", "state": "0"})
        assert pgm.has_valid_identity() is False

    def test_identity_not_based_on_name(self) -> None:
        pgm1 = _make_pgm({"name": "Alpha"})
        pgm2 = _make_pgm({"name": "Beta"})
        assert pgm1.stable_id == pgm2.stable_id

    def test_identity_not_based_on_zone_id(self) -> None:
        pgm1 = _make_pgm({"zoneID": "11"})
        pgm2 = _make_pgm({"zoneID": "99"})
        assert pgm1.stable_id == pgm2.stable_id


class TestPgmRawState:
    def test_raw_state_zero(self) -> None:
        pgm = _make_pgm({"state": "0"})
        assert pgm.raw_state == "0"

    def test_raw_state_one(self) -> None:
        pgm = _make_pgm({"state": "1"})
        assert pgm.raw_state == "1"

    def test_raw_state_preserved_exactly(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = _make_pgm({"state": "unexpected_value"})
        assert pgm.raw_state == "unexpected_value"

    def test_raw_state_empty_when_missing(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0"})
        assert pgm.raw_state == ""


class TestPgmNoBooleanInterpretation:
    def test_no_is_on_attribute(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "is_on")

    def test_no_is_open_attribute(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "is_open")

    def test_no_active_attribute(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "active")


class TestPgmUpdate:
    def test_name_update_without_identity_change(self) -> None:
        pgm = _make_pgm()
        original_id = pgm.stable_id
        pgm.update({"name": "New Name"})
        assert pgm.name == "New Name"
        assert pgm.stable_id == original_id

    def test_zone_metadata_update_without_identity_change(self) -> None:
        pgm = _make_pgm()
        original_id = pgm.stable_id
        pgm.update({"zoneID": "99"})
        assert pgm.zone_id == "99"
        assert pgm.stable_id == original_id

    def test_state_update(self) -> None:
        pgm = _make_pgm({"state": "0"})
        pgm.update({"state": "1"})
        assert pgm.raw_state == "1"

    def test_update_emits_pgm_update_notification(self) -> None:
        pgm = _make_pgm({"state": "0"})
        callback = MagicMock()
        pgm.register(QolsysNotification.PGM_UPDATE, callback)
        pgm.update({"state": "1"})
        callback.assert_called_once()

    def test_update_no_notification_when_unchanged(self) -> None:
        pgm = _make_pgm({"state": "0"})
        callback = MagicMock()
        pgm.register(QolsysNotification.PGM_UPDATE, callback)
        pgm.update({"state": "0"})
        callback.assert_not_called()


class TestPgmZoneIdVariants:
    def test_accepts_zoneID(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "zoneID": "11"})
        assert pgm.zone_id == "11"

    def test_accepts_w2w_zoneID(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "w2w_zoneID": "12"})
        assert pgm.zone_id == "12"

    def test_prefers_zoneID_over_w2w_zoneID(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "zoneID": "11", "w2w_zoneID": "12"})
        assert pgm.zone_id == "11"


class TestPgmNoOutbound:
    def test_no_turn_on_method(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "turn_on")

    def test_no_turn_off_method(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "turn_off")

    def test_no_open_method(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "open")

    def test_no_close_method(self) -> None:
        pgm = _make_pgm()
        assert not hasattr(pgm, "close")


class TestPgmIdentityNormalization:
    """Verify conservative identity normalization: str().strip()."""

    def test_integer_partition_id_normalized(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": 0, "pgm_number": 1, "name": "V", "state": "0"})  # type: ignore[dict-item]
        assert pgm.stable_id == ("0", "1")
        assert pgm.has_valid_identity() is True

    def test_whitespace_stripped(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": " 0 ", "pgm_number": " 1 ", "name": "V", "state": "0"})
        assert pgm.stable_id == ("0", "1")

    def test_whitespace_only_is_invalid(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "  ", "pgm_number": "  ", "name": "V", "state": "0"})
        assert pgm.has_valid_identity() is False

    def test_leading_zeros_preserved(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "01", "name": "V", "state": "0"})
        assert pgm.stable_id == ("0", "01")

    def test_leading_zeros_distinct_from_no_zeros(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm_a = QolsysPgmOutput({"partition_id": "0", "pgm_number": "01", "name": "V", "state": "0"})
        pgm_b = QolsysPgmOutput({"partition_id": "0", "pgm_number": "1", "name": "V", "state": "0"})
        assert pgm_a.stable_id != pgm_b.stable_id

    def test_none_becomes_empty(self) -> None:
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"name": "V", "state": "0"})  # no partition_id/pgm_number keys
        assert pgm.partition_id == ""
        assert pgm.pgm_number == ""
        assert pgm.has_valid_identity() is False

    def test_integer_string_equivalence(self) -> None:
        """Integer 0 and string "0" normalize to the same identity."""
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm_int = QolsysPgmOutput({"partition_id": 0, "pgm_number": 1, "name": "V", "state": "0"})  # type: ignore[dict-item]
        pgm_str = QolsysPgmOutput({"partition_id": "0", "pgm_number": "1", "name": "V", "state": "0"})
        assert pgm_int.stable_id == pgm_str.stable_id
