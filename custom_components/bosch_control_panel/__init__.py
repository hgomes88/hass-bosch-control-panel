"""The bosch_control_panel integration."""
import asyncio
import logging

from bosch.control_panel.cc880p.cp import CP
from bosch.control_panel.cc880p.models.cp import CpVersion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_HOST,
    CONF_INSTALLER_CODE,
    CONF_MODEL,
    CONF_POLLING_PERIOD,
    CONF_PORT,
    DATA_BOSCH,
    DEVICE_ID,
    DOMAIN,
    HW_VERSION,
    MANUFACTURER,
    MODEL,
    PLATFORMS,
    SW_VERSION,
    TITLE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entry function during initialization of bosch control panel.

    Args:
        hass (HomeAssistant): Homeassistant object
        entry (ConfigEntry): Configuration needed for the initialization of the
            control panel

    Returns:
        bool: Return True if the setup was successfully done. False otherwise
    """

    _LOGGER.info("Async Setup Entry Start")

    # Default data is empty
    hass.data.setdefault(DOMAIN, {})

    # Create the control panel
    _alarm = await CP(
        ip=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        model=CpVersion[entry.data[CONF_MODEL]].value,
        installer_code=entry.data[CONF_INSTALLER_CODE],
        poll_period=entry.data[CONF_POLLING_PERIOD] / 1000,
        loop=hass.loop,
    ).start()

    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    hass.data[DOMAIN][entry.entry_id] = {DATA_BOSCH: _alarm}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Async Load Entry Done")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.info("Async Unload Entry Start")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _alarm: CP = hass.data[DOMAIN].pop(entry.entry_id)[DATA_BOSCH]
        await _alarm.stop()
        _LOGGER.info("Async Unload Entry Done")
    else:
        _LOGGER.error("Async Unload Entry Error")

    return unload_ok


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update the currently available control panel.

    Args:
        hass (HomeAssistant): The Homeassistant object
        entry (ConfigEntry): The options needed to update the control panel
    """
    _LOGGER.info("Update the configuration")
    entry.data = entry.options
    await hass.config_entries.async_reload(entry.entry_id)


class BoschControlPanelDevice(Entity):
    """Class used to link all the control panel etities into a device."""

    def __init__(self) -> None:
        """Initialize Bosh Alarm device object."""
        self._available: bool = False
        self._timer: _Timer | None = None

    @property
    def device_info(self) -> dict[str, str]:
        """Get the device information.

        Returns:
            dict[str, str]: THe dictionary with the information of the device
        """
        return {
            "identifiers": {(DOMAIN, DEVICE_ID)},
            "name": TITLE,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": SW_VERSION,
            "hw_version": HW_VERSION,
            "via_device": "none",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def _set_unavailability_timer(self):
        TIMEOUT = 15
        if not self._timer or self._timer.cancelled:
            self._timer = _Timer(TIMEOUT, self._set_unavailable)

    async def _cancel_unavailability_timer(self):
        if self._timer and not self._timer.cancelled:
            self._timer.cancel()
        self._timer = None

    async def _set_available(self):
        await self._set_availability(True)

    async def _set_unavailable(self):
        await self._set_availability(False)

    async def _set_availability(self, available: bool):
        self._available = available
        await self.async_update_ha_state(force_refresh=True)

    async def _update_availability(self, available: bool):
        if available:
            # Cancel timer
            await self._cancel_unavailability_timer()
            await self._set_available()
        else:
            # Set timer
            await self._set_unavailability_timer()


class _Timer:
    def __init__(self, timeout: float, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()
        self._task.cancel()

    def cancel(self):
        """Cancel the timer."""
        self._task.cancel()

    @property
    def cancelled(self):
        """Whether the timer is cancelled."""
        return self._task.cancelled()
