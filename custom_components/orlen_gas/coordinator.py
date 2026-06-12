import logging
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.const import UnitOfVolume
from datetime import timedelta
from .api import OrlenGasApi, AuthError, ApiError
from .usage import build_usage_data, invoice_is_consumption

_LOGGER = logging.getLogger(__name__)

STATISTIC_ID = "orlen_gas:gas_consumption_m3"


class OrlenGasCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, email: str, password: str):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="orlen_gas",
            update_interval=timedelta(hours=24),
        )
        self.api = OrlenGasApi(email, password)

    async def _async_update_data(self):
        """
        Pobiera dane z API.
        Token jest zapamiętany w self.api — logowanie tylko przy pierwszym
        wywołaniu lub gdy token wygaśnie (api._get obsługuje to automatycznie).
        """
        try:
            invoices_data = await self.hass.async_add_executor_job(
                self.api.get_invoices
            )
            balance_data = await self.hass.async_add_executor_job(
                self.api.get_balance
            )
            ppg_list_data = await self.hass.async_add_executor_job(
                self.api.get_ppg_list
            )
        except AuthError as err:
            raise UpdateFailed(f"Błąd autoryzacji: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Błąd API: {err}") from err

        # Pobierz ppg_id z listy PPG
        ppg_id = None
        ppg_list = ppg_list_data if isinstance(ppg_list_data, list) else ppg_list_data.get("PpgList", [])
        if ppg_list:
            ppg_id = ppg_list[0].get("IdPPG") or ppg_list[0].get("Id")

        # Pobierz odczyty licznika dla Energy Dashboard
        meter_reading = None
        if ppg_id:
            try:
                readings_data = await self.hass.async_add_executor_job(
                    self.api.get_meter_readings, ppg_id
                )
                VALID_TYPES = {"Receiver", "RealCorrect"}
                readings = readings_data if isinstance(readings_data, list) else readings_data.get("MeterReadings", [])
                real_readings = [
                    r for r in readings
                    if r.get("Type") in VALID_TYPES and r.get("Value") is not None
                ]
                if real_readings:
                    real_readings.sort(key=lambda r: r.get("ReadingDateLocal", ""), reverse=True)
                    meter_reading = real_readings[0].get("Value")
            except (AuthError, ApiError) as err:
                _LOGGER.warning("Nie udało się pobrać odczytów licznika: %s", err)

        invoice_list = invoices_data.get("InvoicesList", [])
        usage = build_usage_data(invoice_list)
        consumption_invoices = [i for i in invoice_list if invoice_is_consumption(i)]
        last_invoice = consumption_invoices[0] if consumption_invoices else None

        # Zapisz statystyki miesięczne do bazy HA (Energy Dashboard)
        await self._insert_statistics(usage.get("monthly_usage", {}))

        return {
            **usage,
            "balance": balance_data.get("Value"),
            "last_invoice": last_invoice,
            "meter_reading": meter_reading,
        }

    async def _insert_statistics(self, monthly_usage: dict) -> None:
        """
        Wstawia miesięczne zużycie m³ jako zewnętrzne statystyki do bazy HA.
        Każdy miesiąc = jeden rekord z datą początku miesiąca (UTC).
        HA deduplikuje rekordy po start — bezpieczne przy wielokrotnym wywołaniu.
        """
        if not monthly_usage:
            return

        metadata = StatisticMetaData(
            statistic_id=STATISTIC_ID,
            source="orlen_gas",
            name="ORLEN Gas zużycie m³",
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
            has_mean=False,
            has_sum=True,
        )

        statistics = []
        cumulative_sum = 0.0

        for month_key in sorted(monthly_usage.keys()):
            value = monthly_usage[month_key]
            cumulative_sum += value
            # Data początku miesiąca w UTC
            start = datetime.strptime(month_key, "%Y-%m").replace(tzinfo=timezone.utc)
            statistics.append(
                StatisticData(
                    start=start,
                    sum=round(cumulative_sum, 1),
                    state=value,
                )
            )

        async_add_external_statistics(self.hass, metadata, statistics)
        _LOGGER.debug("Wstawiono %d rekordów statystyk dla %s", len(statistics), STATISTIC_ID)
