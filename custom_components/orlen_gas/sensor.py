import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        # Stan licznika (Energy Dashboard)
        OrlenGasMeterReadingSensor(coordinator),
        # Saldo
        OrlenGasBalanceSensor(coordinator),
        # Ostatnia faktura
        OrlenGasLastInvoiceAmountSensor(coordinator),
        OrlenGasLastInvoiceDateSensor(coordinator),
        # Roczne zużycie (suma 12 miesięcy)
        OrlenGasYearConsumptionSensor(coordinator),
        # Miesięczne zużycie — ostatnie 12 miesięcy
        *[
            OrlenGasMonthSensor(coordinator, offset)
            for offset in range(12)
        ],
    ]

    async_add_entities(entities)


class _OrlenGasBase(CoordinatorEntity, SensorEntity):
    """Bazowa klasa dla sensorów ORLEN Gas."""

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "orlen_gas")},
            "name": "ORLEN Gas",
            "manufacturer": "ORLEN",
            "model": "myORLEN API",
        }


class OrlenGasBalanceSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Saldo"
    _attr_unique_id = "orlen_gas_balance"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "PLN"
    _attr_icon = "mdi:cash"

    @property
    def native_value(self):
        return self.coordinator.data.get("balance")


class OrlenGasLastInvoiceAmountSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Ostatnia faktura"
    _attr_unique_id = "orlen_gas_last_invoice_amount"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "PLN"
    _attr_icon = "mdi:file-document-outline"

    @property
    def native_value(self):
        inv = self.coordinator.data.get("last_invoice")
        if inv is None:
            return None
        return inv.get("GrossAmount")

    @property
    def extra_state_attributes(self):
        inv = self.coordinator.data.get("last_invoice")
        if inv is None:
            return {}
        return {
            "number": inv.get("Number"),
            "start_date": inv.get("StartDate"),
            "end_date": inv.get("EndDate"),
            "wear_m3": inv.get("WearM3"),
            "wear_kwh": inv.get("WearKWH"),
            "is_paid": inv.get("IsPaid"),
            "amount_to_pay": inv.get("AmountToPay"),
        }


class OrlenGasLastInvoiceDateSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Data ostatniej faktury"
    _attr_unique_id = "orlen_gas_last_invoice_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar"

    @property
    def native_value(self):
        inv = self.coordinator.data.get("last_invoice")
        if inv is None:
            return None
        end_date = inv.get("EndDate")
        if not end_date:
            return None
        try:
            return datetime.fromisoformat(
                end_date.replace("Z", "+00:00")
            ).date()
        except Exception:
            return None


class OrlenGasYearConsumptionSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Zużycie roczne"
    _attr_unique_id = "orlen_gas_year_consumption"
    _attr_device_class = SensorDeviceClass.GAS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:fire"

    @property
    def native_value(self):
        stats = self.coordinator.data.get("statistics", {})
        return stats.get("sum_12_months")

    @property
    def extra_state_attributes(self):
        stats = self.coordinator.data.get("statistics", {})
        settlements = self.coordinator.data.get("settlements", [])
        return {
            "average_month_m3": stats.get("average_month"),
            "max_month_m3": stats.get("max_month"),
            "min_month_m3": stats.get("min_month"),
            "settlement_months": settlements,
        }


class OrlenGasMonthSensor(_OrlenGasBase):
    _attr_device_class = SensorDeviceClass.GAS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator, month_offset: int):
        super().__init__(coordinator)
        self._month_offset = month_offset

        if month_offset == 0:
            label = "biezacy_miesiac"
            name = "ORLEN Gas Bieżący miesiąc"
        elif month_offset == 1:
            label = "poprzedni_miesiac"
            name = "ORLEN Gas Poprzedni miesiąc"
        else:
            label = f"miesiac_minus_{month_offset}"
            name = f"ORLEN Gas Miesiąc -{month_offset}"

        self._attr_unique_id = f"orlen_gas_{label}_m3"
        self._attr_name = name

    def _get_month_entry(self):
        monthly = self.coordinator.data.get("monthly_usage", {})
        items = sorted(monthly.items())  # lista (month_key, value)
        idx = -(self._month_offset + 1)
        if len(items) < abs(idx):
            return None, None
        key, value = items[idx]
        return key, value

    @property
    def native_value(self):
        _, value = self._get_month_entry()
        return value

    @property
    def extra_state_attributes(self):
        key, _ = self._get_month_entry()
        settlements = self.coordinator.data.get("settlements", [])
        return {
            "month": key,
            "is_settlement": key in settlements if key else False,
        }


class OrlenGasMeterReadingSensor(_OrlenGasBase):
    """
    Stan licznika gazu — rosnący odczyt w m³.
    Używany przez Energy Dashboard (device_class=GAS, state_class=TOTAL_INCREASING).
    Pobierany z get-all-ppg-readings-for-meter, tylko odczyty Receiver i RealCorrect.
    """
    _attr_name = "ORLEN Gas Stan licznika"
    _attr_unique_id = "orlen_gas_meter_reading"
    _attr_device_class = SensorDeviceClass.GAS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:meter-gas"

    @property
    def native_value(self):
        return self.coordinator.data.get("meter_reading")
