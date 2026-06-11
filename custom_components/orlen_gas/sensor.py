import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
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
        # Roczne zużycie m³ / kWh / PLN
        OrlenGasYearConsumptionSensor(coordinator),
        OrlenGasYearKwhSensor(coordinator),
        OrlenGasYearCostSensor(coordinator),
        # Miesięczne zużycie m³ — ostatnie 12 miesięcy
        *[OrlenGasMonthSensor(coordinator, offset) for offset in range(12)],
        # Miesięczne zużycie kWh — ostatnie 12 miesięcy
        *[OrlenGasMonthKwhSensor(coordinator, offset) for offset in range(12)],
        # Miesięczny koszt PLN — ostatnie 12 miesięcy
        *[OrlenGasMonthCostSensor(coordinator, offset) for offset in range(12)],
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


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

class OrlenGasBalanceSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Saldo"
    _attr_unique_id = "orlen_gas_balance"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "PLN"
    _attr_icon = "mdi:cash"

    @property
    def native_value(self):
        return self.coordinator.data.get("balance")


# ---------------------------------------------------------------------------
# Faktury
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Roczne agregaty
# ---------------------------------------------------------------------------

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


class OrlenGasYearKwhSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Zużycie roczne kWh"
    _attr_unique_id = "orlen_gas_year_kwh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self):
        return self.coordinator.data.get("statistics", {}).get("sum_12_months_kwh")


class OrlenGasYearCostSensor(_OrlenGasBase):
    _attr_name = "ORLEN Gas Koszt roczny"
    _attr_unique_id = "orlen_gas_year_cost"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "PLN"
    _attr_icon = "mdi:cash-multiple"

    @property
    def native_value(self):
        return self.coordinator.data.get("statistics", {}).get("sum_12_months_pln")


# ---------------------------------------------------------------------------
# Miesięczne zużycie m³
# ---------------------------------------------------------------------------

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
        items = sorted(monthly.items())
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


# ---------------------------------------------------------------------------
# Miesięczne zużycie kWh
# ---------------------------------------------------------------------------

class OrlenGasMonthKwhSensor(_OrlenGasBase):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, month_offset: int):
        super().__init__(coordinator)
        self._month_offset = month_offset

        if month_offset == 0:
            label = "biezacy_miesiac"
            name = "ORLEN Gas kWh bieżący miesiąc"
        elif month_offset == 1:
            label = "poprzedni_miesiac"
            name = "ORLEN Gas kWh poprzedni miesiąc"
        else:
            label = f"miesiac_minus_{month_offset}"
            name = f"ORLEN Gas kWh miesiąc -{month_offset}"

        self._attr_unique_id = f"orlen_gas_{label}_kwh"
        self._attr_name = name

    def _get_entry(self):
        monthly = self.coordinator.data.get("monthly_kwh", {})
        items = sorted(monthly.items())
        idx = -(self._month_offset + 1)
        if len(items) < abs(idx):
            return None, None
        return items[idx]

    @property
    def native_value(self):
        _, value = self._get_entry()
        return value

    @property
    def extra_state_attributes(self):
        key, _ = self._get_entry()
        return {"month": key}


# ---------------------------------------------------------------------------
# Miesięczny koszt PLN
# ---------------------------------------------------------------------------

class OrlenGasMonthCostSensor(_OrlenGasBase):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "PLN"
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, month_offset: int):
        super().__init__(coordinator)
        self._month_offset = month_offset

        if month_offset == 0:
            label = "biezacy_miesiac"
            name = "ORLEN Gas Koszt bieżący miesiąc"
        elif month_offset == 1:
            label = "poprzedni_miesiac"
            name = "ORLEN Gas Koszt poprzedni miesiąc"
        else:
            label = f"miesiac_minus_{month_offset}"
            name = f"ORLEN Gas Koszt miesiąc -{month_offset}"

        self._attr_unique_id = f"orlen_gas_{label}_pln"
        self._attr_name = name

    def _get_entry(self):
        monthly = self.coordinator.data.get("monthly_costs", {})
        items = sorted(monthly.items())
        idx = -(self._month_offset + 1)
        if len(items) < abs(idx):
            return None, None
        return items[idx]

    @property
    def native_value(self):
        _, value = self._get_entry()
        return value

    @property
    def extra_state_attributes(self):
        key, _ = self._get_entry()
        return {"month": key}


# ---------------------------------------------------------------------------
# Stan licznika
# ---------------------------------------------------------------------------

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
