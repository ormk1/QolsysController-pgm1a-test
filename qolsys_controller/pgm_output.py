"""PGM Output model for Qolsys Controller."""

from __future__ import annotations

import logging
from typing import Any

from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.observable import Event, QolsysObservable

LOGGER = logging.getLogger(__name__)


class QolsysPgmOutput(QolsysObservable):
    """A single PGM output on the Qolsys panel.

    Stable identity is (partition_id, pgm_number).
    Raw state is preserved without boolean conversion.
    """

    @staticmethod
    def _normalize_id(value: object) -> str:
        """Normalize an identity field: str conversion + strip whitespace."""
        return str(value).strip() if value is not None else ""

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__()

        self._partition_id: str = self._normalize_id(data.get("partition_id"))
        self._pgm_number: str = self._normalize_id(data.get("pgm_number"))
        self._name: str = data.get("name", "")
        self._raw_state: str = data.get("state", "")
        # Accept either zoneID or w2w_zoneID
        self._zone_id: str = data.get("zoneID", "") or data.get("w2w_zoneID", "")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def stable_id(self) -> tuple[str, str]:
        """Stable identity tuple: (partition_id, pgm_number)."""
        return (self._partition_id, self._pgm_number)

    def has_valid_identity(self) -> bool:
        """Return True if the object has the minimum fields for a stable identity."""
        return self._partition_id != "" and self._pgm_number != ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def partition_id(self) -> str:
        return self._partition_id

    @property
    def pgm_number(self) -> str:
        return self._pgm_number

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if self._name != value:
            self._name = value
            self.notify(Event(QolsysNotification.PGM_UPDATE, self, self.to_dict_event()))

    @property
    def raw_state(self) -> str:
        return self._raw_state

    @raw_state.setter
    def raw_state(self, value: str) -> None:
        if self._raw_state != value:
            self._raw_state = value
            self.notify(Event(QolsysNotification.PGM_UPDATE, self, self.to_dict_event()))

    @property
    def zone_id(self) -> str:
        return self._zone_id

    @zone_id.setter
    def zone_id(self, value: str) -> None:
        if self._zone_id != value:
            self._zone_id = value
            self.notify(Event(QolsysNotification.PGM_UPDATE, self, self.to_dict_event()))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, data: dict[str, str]) -> None:
        """Update mutable attributes from a dbChanged payload.

        Identity fields are not changed.
        """
        self.start_batch_update()

        if "name" in data:
            self.name = data["name"]

        if "state" in data:
            self.raw_state = data["state"]

        zone_id_value = data.get("zoneID", "") or data.get("w2w_zoneID", "")
        if zone_id_value:
            self.zone_id = zone_id_value

        self.end_batch_update()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, str]:
        """Return a full dictionary representation for diagnostics and sync updates."""
        return {
            "partition_id": self._partition_id,
            "pgm_number": self._pgm_number,
            "name": self._name,
            "state": self._raw_state,
            "zoneID": self._zone_id,
        }

    def to_dict_event(self) -> dict[str, Any]:
        """Return event payload for notification subscribers."""
        return {
            "partition_id": self._partition_id,
            "pgm_number": self._pgm_number,
            "name": self._name,
            "state": self._raw_state,
            "zone_id": self._zone_id,
        }
