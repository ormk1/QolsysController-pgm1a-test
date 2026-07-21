"""Tests for QolsysPanel PGM output loading and dbChanged handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from qolsys_controller.panel import QolsysPanel
from qolsys_controller.pgm_output import QolsysPgmOutput
from qolsys_controller.state import QolsysState

# Synthetic fixture based on observed IQ4 PGM fields.
PGM_URI = "content://com.qolsys.qolsysprovider.PgmOutputsContentProvider/pgm_outputs"


def _make_controller() -> MagicMock:
    controller = MagicMock()
    controller.state = QolsysState(controller)
    controller.settings = MagicMock()
    controller.settings.random_mac = "AA:BB:CC:DD:EE:FF"
    return controller


def _make_panel(controller: MagicMock | None = None) -> QolsysPanel:
    if controller is None:
        controller = _make_controller()
    panel = QolsysPanel(controller)
    return panel


class TestGetPgmOutputsFromDb:
    def test_returns_valid_pgm_objects(self) -> None:
        panel = _make_panel()
        # Synthetic fixture based on observed IQ4 PGM fields.
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "Water Valve", "state": "0", "zoneID": "11"},
            {"partition_id": "0", "pgm_number": "1", "name": "Gas Valve", "state": "1", "zoneID": "12"},
        ])
        result = panel.get_pgm_outputs_from_db()
        assert len(result) == 2
        assert all(isinstance(p, QolsysPgmOutput) for p in result)

    def test_skips_invalid_identity_rows(self) -> None:
        panel = _make_panel()
        # Synthetic fixture based on observed IQ4 PGM fields.
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"name": "Bad Row"},  # Missing identity
            {"partition_id": "0", "pgm_number": "0", "name": "Good", "state": "0"},
        ])
        result = panel.get_pgm_outputs_from_db()
        assert len(result) == 1
        assert result[0].name == "Good"

    def test_empty_db_returns_empty_list(self) -> None:
        panel = _make_panel()
        panel.db.get_pgm_outputs = MagicMock(return_value=[])
        result = panel.get_pgm_outputs_from_db()
        assert result == []


class TestDbChangedUpdate:
    def test_update_existing_pgm_state(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)
        # Pre-add a PGM to state
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "0"})
        controller.state.pgm_output_add(pgm)

        # After DB update, get_pgm_outputs returns refreshed row
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "1"},
        ])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"state": "1"},
        }
        panel.parse_iq2meid_message(data)

        assert pgm.raw_state == "1"
        # Original object is preserved
        assert controller.state.pgm_output("0", "0") is pgm

    def test_update_creates_new_if_not_in_state(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)

        # DB has a row that state doesn't know about yet
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "New", "state": "1"},
        ])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"partition_id": "0", "pgm_number": "0", "name": "New", "state": "1"},
        }
        panel.parse_iq2meid_message(data)

        assert controller.state.pgm_output("0", "0") is not None
        assert controller.state.pgm_output("0", "0").raw_state == "1"

    def test_partial_update_without_identity_fields(self) -> None:
        """contentValues contains only 'state' — no partition_id or pgm_number."""
        controller = _make_controller()
        panel = _make_panel(controller)
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "0"})
        controller.state.pgm_output_add(pgm)

        # DB reflects the update
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "1"},
        ])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"state": "1"},  # No identity fields
        }
        panel.parse_iq2meid_message(data)

        # Object is updated in place
        assert pgm.raw_state == "1"
        assert controller.state.pgm_output("0", "0") is pgm
        assert len(controller.state.pgm_outputs) == 1


class TestDbChangedInsert:
    def test_insert_adds_pgm(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)

        # Synthetic fixture based on observed IQ4 PGM fields.
        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "insert",
            "uri": PGM_URI,
            "contentValues": {"partition_id": "0", "pgm_number": "0", "name": "Water Valve", "state": "0", "zoneID": "11"},
        }
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.parse_iq2meid_message(data)

        assert controller.state.pgm_output("0", "0") is not None
        assert controller.state.pgm_output("0", "0").name == "Water Valve"

    def test_insert_invalid_identity_ignored(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "insert",
            "uri": PGM_URI,
            "contentValues": {"name": "Bad"},
        }
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.parse_iq2meid_message(data)

        assert len(controller.state.pgm_outputs) == 0

    def test_insert_duplicate_updates_existing(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Original", "state": "0"})
        controller.state.pgm_output_add(pgm)

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "insert",
            "uri": PGM_URI,
            "contentValues": {"partition_id": "0", "pgm_number": "0", "name": "Duplicate", "state": "1"},
        }
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.parse_iq2meid_message(data)

        # Should still be one PGM, updated
        assert len(controller.state.pgm_outputs) == 1
        assert pgm.name == "Duplicate"


class TestDbChangedDelete:
    def test_delete_removes_pgm_via_sync(self) -> None:
        controller = _make_controller()
        panel = _make_panel(controller)
        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "0"})
        controller.state.pgm_output_add(pgm)

        # After delete, get_pgm_outputs_from_db returns empty
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "delete",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
        }
        panel.parse_iq2meid_message(data)

        assert len(controller.state.pgm_outputs) == 0


class TestPgmUriNoLongerUnknown:
    """The PGM URI must be handled and NOT fall through to unknown-uri log."""

    def test_update_does_not_log_unknown(self) -> None:
        panel = _make_panel()
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"partition_id": "0", "pgm_number": "0", "state": "1"},
        }
        with patch("qolsys_controller.panel.LOGGER") as mock_logger:
            panel.parse_iq2meid_message(data)
            # Should NOT log "unknow uri"
            for call in mock_logger.debug.call_args_list:
                assert "unknow uri" not in str(call)

    def test_insert_does_not_log_unknown(self) -> None:
        panel = _make_panel()
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "insert",
            "uri": PGM_URI,
            "contentValues": {"partition_id": "0", "pgm_number": "0", "name": "V", "state": "0"},
        }
        with patch("qolsys_controller.panel.LOGGER") as mock_logger:
            panel.parse_iq2meid_message(data)
            for call in mock_logger.debug.call_args_list:
                assert "unknow uri" not in str(call)

    def test_delete_does_not_log_unknown(self) -> None:
        panel = _make_panel()
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "delete",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
        }
        with patch("qolsys_controller.panel.LOGGER") as mock_logger:
            panel.parse_iq2meid_message(data)
            for call in mock_logger.debug.call_args_list:
                assert "unknown uri" not in str(call)


class TestPartialUpdateNotifications:
    """Verify partial update emits correct notifications via DB reconciliation."""

    def test_partial_update_emits_one_pgm_update(self) -> None:
        """Synthetic fixture based on observed IQ4 PGM fields."""
        controller = _make_controller()
        panel = _make_panel(controller)
        from qolsys_controller.enum_qolsys import QolsysNotification

        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "0"})
        controller.state.pgm_output_add(pgm)

        update_callback = MagicMock()
        add_callback = MagicMock()
        pgm.register(QolsysNotification.PGM_UPDATE, update_callback)
        controller.state.register(QolsysNotification.PGM_ADD, add_callback)

        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "1"},
        ])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"state": "1"},
        }
        panel.parse_iq2meid_message(data)

        update_callback.assert_called_once()
        add_callback.assert_not_called()

    def test_duplicate_partial_update_emits_no_notification(self) -> None:
        """Synthetic fixture based on observed IQ4 PGM fields."""
        controller = _make_controller()
        panel = _make_panel(controller)
        from qolsys_controller.enum_qolsys import QolsysNotification

        pgm = QolsysPgmOutput({"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "1"})
        controller.state.pgm_output_add(pgm)

        update_callback = MagicMock()
        pgm.register(QolsysNotification.PGM_UPDATE, update_callback)

        # DB still returns state "1" — no change
        panel.db.table_pgm_outputs = MagicMock()
        panel.db.table_pgm_outputs.uri = PGM_URI
        panel.db.get_pgm_outputs = MagicMock(return_value=[
            {"partition_id": "0", "pgm_number": "0", "name": "Valve", "state": "1"},
        ])

        data: dict = {
            "eventName": "dbChanged",
            "dbOperation": "update",
            "uri": PGM_URI,
            "selection": "_id=?",
            "selectionArgs": "1",
            "contentValues": {"state": "1"},
        }
        panel.parse_iq2meid_message(data)

        update_callback.assert_not_called()
