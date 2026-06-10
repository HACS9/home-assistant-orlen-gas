import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import OrlenGasApi, AuthError, ApiError
from .usage import build_usage_data, invoice_is_consumption

_LOGGER = logging.getLogger(__name__)


class OrlenGasCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, email: str, password: str):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="orlen_gas",
            update_interval=timedelta(hours=24),
        )
        # api trzyma token w pamięci między odświeżeniami
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
        except AuthError as err:
            raise UpdateFailed(f"Błąd autoryzacji: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Błąd API: {err}") from err

        invoice_list = invoices_data.get("InvoicesList", [])
        usage = build_usage_data(invoice_list)

        consumption_invoices = [i for i in invoice_list if invoice_is_consumption(i)]
        last_invoice = consumption_invoices[0] if consumption_invoices else None

        return {
            **usage,
            "balance": balance_data.get("Value"),
            "last_invoice": last_invoice,
        }
