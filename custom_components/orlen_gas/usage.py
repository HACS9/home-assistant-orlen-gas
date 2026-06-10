from datetime import datetime
from collections import defaultdict


def invoice_is_consumption(invoice):
    """
    Pomijamy:
    - noty odsetkowe
    - korekty
    - rekordy bez zużycia
    """

    if invoice.get("WearKWH", 0) <= 0:
        return False

    if invoice.get("Type") != "PPG":
        return False

    return True


def build_monthly_usage(invoice_list):
    """
    Zamienia faktury ORLEN na zużycie miesięczne.

    Zwraca:
    {
        "2025-04": 75.0,
        "2025-05": 102.0,
        ...
    }
    """

    monthly = defaultdict(float)

    for invoice in invoice_list:

        if not invoice_is_consumption(invoice):
            continue

        start_date = invoice.get("StartDate")
        end_date = invoice.get("EndDate")

        usage = invoice.get("WearM3")

        if usage is None:
            continue

        try:
            start = datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            )

            end = datetime.fromisoformat(
                end_date.replace("Z", "+00:00")
            )

        except Exception:
            continue

        days = (end - start).days + 1

        if days <= 0:
            continue

        daily_usage = usage / days

        current = start

        while current <= end:

            month_key = current.strftime("%Y-%m")

            monthly[month_key] += daily_usage

            current = current.replace(day=current.day) + \
                __import__("datetime").timedelta(days=1)

    return {
        month: round(value, 1)
        for month, value in sorted(monthly.items())
    }


def detect_settlements(monthly_usage):
    """
    Wykrywa wyrównania.

    MVP:
    miesiąc > 3x średnia
    """

    values = list(monthly_usage.values())

    if not values:
        return []

    average = sum(values) / len(values)

    settlements = []

    for month, value in monthly_usage.items():

        if value > average * 3:
            settlements.append(month)

    return settlements


def build_statistics(monthly_usage):

    values = list(monthly_usage.values())

    if not values:
        return {}

    return {
        "current_month": values[-1],
        "last_month": values[-2] if len(values) > 1 else None,
        "sum_12_months": round(sum(values[-12:]), 1),
        "average_month": round(sum(values) / len(values), 1),
        "max_month": max(values),
        "min_month": min(values),
    }

def build_usage_data(invoice_list):
    """
    Główna funkcja wywoływana przez coordinator.
    Zwraca słownik gotowy do przekazania sensorom.
    """

    monthly_usage = build_monthly_usage(invoice_list)
    settlements = detect_settlements(monthly_usage)
    statistics = build_statistics(monthly_usage)

    return {
        "monthly_usage": monthly_usage,
        "settlements": settlements,
        "statistics": statistics,
    }
