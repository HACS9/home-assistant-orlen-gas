import logging
import requests

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://ebok.myorlen.pl"


class AuthError(Exception):
    """Nieprawidłowe dane logowania."""


class ApiError(Exception):
    """Błąd komunikacji z API."""


class OrlenGasApi:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.token = None

    def login(self):
        """
        Logowanie i zapamiętanie tokena w sesji.
        Wywoływane raz — przy konfiguracji i po wygaśnięciu tokena.
        """
        url = f"{BASE_URL}/auth/login?api-version=3.0"
        payload = {
            "identificator": self.email,
            "accessPin": self.password,
            "rememberLogin": False,
            "DeviceId": "123",
            "DeviceName": "Python Test",
            "DeviceType": "Web",
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as err:
            raise ApiError(f"Błąd połączenia: {err}") from err

        if response.status_code == 401:
            raise AuthError("Nieprawidłowy login lub hasło")

        response.raise_for_status()

        data = response.json()
        token = data.get("Token")
        if not token:
            raise AuthError("Brak tokena w odpowiedzi API")

        self.token = token
        _LOGGER.debug("Zalogowano do myORLEN")
        return token

    def _get(self, path: str):
        """
        Wykonuje GET z aktualnym tokenem.
        Jeśli token wygasł (401) — loguje się ponownie i ponawia raz.
        """
        if not self.token:
            self.login()

        url = f"{BASE_URL}{path}"
        headers = {
            "Accept": "application/json",
            "AuthToken": self.token,
        }
        try:
            response = self.session.get(url, headers=headers, timeout=30)
        except requests.RequestException as err:
            raise ApiError(f"Błąd połączenia: {err}") from err

        if response.status_code == 401:
            # Token wygasł — odśwież i spróbuj jeszcze raz
            _LOGGER.debug("Token wygasł, ponawiam logowanie")
            self.login()
            headers["AuthToken"] = self.token
            try:
                response = self.session.get(url, headers=headers, timeout=30)
            except requests.RequestException as err:
                raise ApiError(f"Błąd połączenia: {err}") from err

        response.raise_for_status()
        return response.json()

    def get_ppg_list(self):
        return self._get("/crm/get-ppg-list?api-version=3.0")

    def get_meter_readings(self, ppg_id: str):
        """
        Pobiera historię odczytów licznika dla danego PPG.
        Endpoint: /crm/get-all-ppg-readings-for-meter
        Zwraca listę odczytów, każdy z polami Value, Type, ReadingDateLocal.
        """
        return self._get(
            f"/crm/get-all-ppg-readings-for-meter"
            f"?pageSize=500&pageNumber=1&api-version=3.0&idPpg={ppg_id}"
        )


    def get_invoices(self):
        return self._get(
            "/crm/get-invoices-v2"
            "?pageNumber=1"
            "&pageSize=100"
            "&api-version=3.0"
        )

    def get_balance(self):
        return self._get("/crm/get-balance?api-version=3.0")

    def get_agreements(self):
        return self._get("/crm/get-agreements?api-version=3.0")