from datetime import datetime
from collections import defaultdict


def _parse_date(date_str):
    """Parsuje datę ISO z opcjonalnym 'Z' na końcu."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


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

    WearM3 z każdej faktury przypisywane jest bezpośrednio
    do miesiąca z EndDate (bez rozkładu na dni).

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

        usage = invoice.get("WearM3")
        if usage is None:
            continue

        end = _parse_date(invoice.get("EndDate"))
        if end is None:
            continue

        month_key = end.strftime("%Y-%m")
        monthly[month_key] += usage

    return {
        month: round(value, 1)
        for month, value in sorted(monthly.items())
    }


def detect_settlements(monthly_usage):
    """
    Wykrywa wyrównania.

    MVP: miesiąc > 3x średnia
    """
    values = list(monthly_usage.values())

    if not values:
        return []

    average = sum(values) / len(values)

    return [
        month
        for month, value in monthly_usage.items()
        if value > average * 3
    ]


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
