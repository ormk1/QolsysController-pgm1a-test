"""Tests for QolsysState PGM output collection, sync, add, and delete."""

from __future__ import annotations

from unittest.mock import MagicMock

from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.pgm_output import QolsysPgmOutput
from qolsys_controller.state import QolsysState


# Synthetic fixture based on observed IQ4 PGM fields.
def _make_pgm(partition_id: str = "0", pgm_number: str = "0", name: str = "PGM Test", state: str = "0") -> QolsysPgmOutput:
    return QolsysPgmOutput({
        "partition_id": partition_id,
        "pgm_number": pgm_number,
        "name": name,
        "state": state,
        "zoneID": "11",
    })


def _make_state() -> QolsysState:
    return QolsysState(MagicMock())


class TestPgmOutputAdd:
    def test_add_single(self) -> None:
        state = _make_state()
        pgm = _make_pgm()
        state.pgm_output_add(pgm)
        assert len(state.pgm_outputs) == 1
        assert state.pgm_output("0", "0") is pgm

    def test_add_emits_pgm_add_notification(self) -> None:
        state = _make_state()
        callback = MagicMock()
        state.register(QolsysNotification.PGM_ADD, callback)
        pgm = _make_pgm()
        state.pgm_output_add(pgm)
        callback.assert_called_once()

    def test_add_duplicate_updates_existing(self) -> None:
        state = _make_state()
        pgm1 = _make_pgm(name="First")
        state.pgm_output_add(pgm1)
        pgm2 = _make_pgm(name="Second")
        state.pgm_output_add(pgm2)
        # Only one PGM exists
        assert len(state.pgm_outputs) == 1
        # Original object is kept, updated with new data
        assert state.pgm_output("0", "0") is pgm1
        assert state.pgm_output("0", "0").name == "Second"

    def test_add_invalid_identity_ignored(self) -> None:
        state = _make_state()
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"name": "No ID"})
        state.pgm_output_add(pgm)
        assert len(state.pgm_outputs) == 0

    def test_add_multiple_different_ids(self) -> None:
        state = _make_state()
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="0"))
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="1"))
        state.pgm_output_add(_make_pgm(partition_id="1", pgm_number="0"))
        assert len(state.pgm_outputs) == 3


class TestPgmOutputDelete:
    def test_delete_existing(self) -> None:
        state = _make_state()
        pgm = _make_pgm()
        state.pgm_output_add(pgm)
        state.pgm_output_delete("0", "0")
        assert len(state.pgm_outputs) == 0

    def test_delete_emits_pgm_delete_notification(self) -> None:
        state = _make_state()
        callback = MagicMock()
        state.register(QolsysNotification.PGM_DELETE, callback)
        pgm = _make_pgm()
        state.pgm_output_add(pgm)
        state.pgm_output_delete("0", "0")
        callback.assert_called_once()

    def test_delete_nonexistent_no_error(self) -> None:
        state = _make_state()
        # Should not raise
        state.pgm_output_delete("99", "99")

    def test_delete_nonexistent_no_notification(self) -> None:
        state = _make_state()
        callback = MagicMock()
        state.register(QolsysNotification.PGM_DELETE, callback)
        state.pgm_output_delete("99", "99")
        callback.assert_not_called()


class TestPgmOutputLookup:
    def test_lookup_existing(self) -> None:
        state = _make_state()
        pgm = _make_pgm(partition_id="1", pgm_number="2")
        state.pgm_output_add(pgm)
        assert state.pgm_output("1", "2") is pgm

    def test_lookup_nonexistent_returns_none(self) -> None:
        state = _make_state()
        assert state.pgm_output("9", "9") is None


class TestSyncPgmOutputsData:
    def test_initial_sync_adds_all(self) -> None:
        state = _make_state()
        db_pgms = [
            _make_pgm(partition_id="0", pgm_number="0"),
            _make_pgm(partition_id="0", pgm_number="1"),
        ]
        state.sync_pgm_outputs_data(db_pgms)
        assert len(state.pgm_outputs) == 2

    def test_sync_updates_existing_preserves_identity(self) -> None:
        state = _make_state()
        pgm = _make_pgm(name="Original", state="0")
        state.pgm_output_add(pgm)
        db_pgms = [_make_pgm(name="Updated", state="1")]
        state.sync_pgm_outputs_data(db_pgms)
        # Same object is retained
        assert state.pgm_output("0", "0") is pgm
        assert pgm.name == "Updated"
        assert pgm.raw_state == "1"

    def test_sync_removes_stale(self) -> None:
        state = _make_state()
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="0"))
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="1"))
        # Sync with only one PGM
        state.sync_pgm_outputs_data([_make_pgm(partition_id="0", pgm_number="0")])
        assert len(state.pgm_outputs) == 1
        assert state.pgm_output("0", "1") is None

    def test_sync_empty_removes_all(self) -> None:
        state = _make_state()
        state.pgm_output_add(_make_pgm())
        state.sync_pgm_outputs_data([])
        assert len(state.pgm_outputs) == 0

    def test_sync_skips_invalid_identity(self) -> None:
        state = _make_state()
        # Synthetic fixture based on observed IQ4 PGM fields.
        invalid = QolsysPgmOutput({"name": "Bad"})
        valid = _make_pgm(partition_id="0", pgm_number="0")
        state.sync_pgm_outputs_data([invalid, valid])
        assert len(state.pgm_outputs) == 1

    def test_reconnect_sync_reuses_objects(self) -> None:
        """Simulate reconnect: second sync should reuse first-sync objects."""
        state = _make_state()
        pgm = _make_pgm(partition_id="0", pgm_number="0", state="0")
        state.pgm_output_add(pgm)
        # Simulate reconnect DB with same PGM but updated state
        new_pgm = _make_pgm(partition_id="0", pgm_number="0", state="1")
        state.sync_pgm_outputs_data([new_pgm])
        # Original object is kept
        assert state.pgm_output("0", "0") is pgm
        assert pgm.raw_state == "1"

    def test_reconnect_adds_new_removes_stale(self) -> None:
        """Simulate reconnect: adds new PGMs, removes ones not in fresh sync."""
        state = _make_state()
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="0"))
        state.pgm_output_add(_make_pgm(partition_id="0", pgm_number="1"))
        # Reconnect brings different set
        state.sync_pgm_outputs_data([
            _make_pgm(partition_id="0", pgm_number="1"),
            _make_pgm(partition_id="0", pgm_number="2"),
        ])
        assert state.pgm_output("0", "0") is None
        assert state.pgm_output("0", "1") is not None
        assert state.pgm_output("0", "2") is not None
        assert len(state.pgm_outputs) == 2


class TestIdentityNormalizationAcrossSync:
    """Verify integer/string identity equivalence across load and update cycles."""

    def test_integer_initial_sync_then_string_lookup(self) -> None:
        """Initial sync uses integer IDs, later lookup uses string equivalents."""
        state = _make_state()
        # Synthetic fixture based on observed IQ4 PGM fields.
        pgm = QolsysPgmOutput({"partition_id": 0, "pgm_number": 1, "name": "V", "state": "0"})  # type: ignore[dict-item]
        state.pgm_output_add(pgm)
        # String lookup finds same object
        assert state.pgm_output("0", "1") is pgm

    def test_string_initial_then_integer_sync_reuses_object(self) -> None:
        """Existing string object is reused when sync provides integer equivalents."""
        state = _make_state()
        pgm = _make_pgm(partition_id="0", pgm_number="1", state="0")
        state.pgm_output_add(pgm)
        # Sync with integer-typed identities
        # Synthetic fixture based on observed IQ4 PGM fields.
        new_pgm = QolsysPgmOutput({"partition_id": 0, "pgm_number": 1, "name": "V", "state": "1"})  # type: ignore[dict-item]
        state.sync_pgm_outputs_data([new_pgm])
        # Same object retained, updated
        assert state.pgm_output("0", "1") is pgm
        assert pgm.raw_state == "1"
        assert len(state.pgm_outputs) == 1

    def test_identical_sync_after_normalization_emits_nothing(self) -> None:
        """Identical re-sync produces no notifications."""
        state = _make_state()
        pgm = _make_pgm(partition_id="0", pgm_number="0", name="Valve", state="1")
        state.pgm_output_add(pgm)

        add_cb = MagicMock()
        update_cb = MagicMock()
        delete_cb = MagicMock()
        state.register(QolsysNotification.PGM_ADD, add_cb)
        pgm.register(QolsysNotification.PGM_UPDATE, update_cb)
        state.register(QolsysNotification.PGM_DELETE, delete_cb)

        # Re-sync with identical data
        state.sync_pgm_outputs_data([_make_pgm(partition_id="0", pgm_number="0", name="Valve", state="1")])

        add_cb.assert_not_called()
        update_cb.assert_not_called()
        delete_cb.assert_not_called()
        assert len(state.pgm_outputs) == 1


class TestSharedStateCoexistence:
    """Verify Zone and PGM objects coexist without interference in shared state."""

    def _populate_state(self) -> tuple:
        """Create state with Zone 11, Zone 12, and one PGM with zone_id='11'."""
        from qolsys_controller.zone import QolsysZone

        state = _make_state()

        settings = MagicMock()
        settings.motion_sensor_delay = False
        settings.motion_sensor_delay_sec = 310

        # Synthetic fixture based on observed IQ4 PGM fields.
        zone_11 = QolsysZone(
            {"zoneid": "11", "sensorname": "TakeoverModule", "sensorstatus": "Closed",
             "sensortype": "Door_Window", "sensorgroup": "entryexitdelay", "partition_id": "0"},
            settings,
        )
        zone_12 = QolsysZone(
            {"zoneid": "12", "sensorname": "Input-0 TakeoverModule", "sensorstatus": "Closed",
             "sensortype": "Door_Window", "sensorgroup": "entryexitdelay", "partition_id": "0"},
            settings,
        )
        state.zone_add(zone_11)
        state.zone_add(zone_12)

        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "PGM Out", "state": "0", "zoneID": "11"})
        state.pgm_output_add(pgm)

        return state, zone_11, zone_12, pgm

    def test_all_objects_present(self) -> None:
        state, zone_11, zone_12, pgm = self._populate_state()
        assert state.zone("11") is zone_11
        assert state.zone("12") is zone_12
        assert state.pgm_output("0", "0") is pgm
        assert len(state.zones) == 2
        assert len(state.pgm_outputs) == 1

    def test_pgm_update_does_not_mutate_zones(self) -> None:
        state, zone_11, zone_12, pgm = self._populate_state()
        pgm.update({"state": "1"})
        assert zone_11.sensorstatus == "Closed"
        assert zone_12.sensorstatus == "Closed"
        assert state.zone("11") is zone_11
        assert state.zone("12") is zone_12

    def test_pgm_delete_does_not_remove_zones(self) -> None:
        state, zone_11, zone_12, pgm = self._populate_state()
        state.pgm_output_delete("0", "0")
        assert state.zone("11") is zone_11
        assert state.zone("12") is zone_12
        assert len(state.zones) == 2
        assert len(state.pgm_outputs) == 0

    def test_zone_update_does_not_mutate_pgm(self) -> None:
        state, zone_11, zone_12, pgm = self._populate_state()
        zone_11.update({"zoneid": "11", "sensorstatus": "Open"})
        assert pgm.raw_state == "0"
        assert state.pgm_output("0", "0") is pgm

    def test_zone_delete_does_not_remove_pgm(self) -> None:
        state, zone_11, zone_12, pgm = self._populate_state()
        state.zone_delete("11")
        assert state.pgm_output("0", "0") is pgm
        assert pgm.raw_state == "0"
        assert len(state.pgm_outputs) == 1
