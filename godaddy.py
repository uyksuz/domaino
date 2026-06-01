import os
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)
_BASE = "https://api.godaddy.com/v1"


def _headers():
    key    = os.environ.get("GODADDY_KEY", "")
    secret = os.environ.get("GODADDY_SECRET", "")
    return {
        "Authorization": f"sso-key {key}:{secret}",
        "Accept": "application/json",
    }


def get_appraisal(domain: str) -> Optional[Dict[str, Any]]:
    """GoValue API'den domain degerleme verisi dondurur.
    Basarisizsa None, basarili olursa dict dondurur:
    {goValue, listPrice, goValueWholesale, minPrice, maxPrice,
     salesProbability, salesProbability500}
    """
    try:
        r = requests.get(
            f"{_BASE}/domains/govalues",
            params={"domainName": domain},
            headers=_headers(),
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "OK":
                return {
                    "goValue":               data.get("goValue"),
                    "listPrice":             data.get("listPrice"),
                    "goValueWholesale":      data.get("goValueWholesale"),
                    "minPrice":              data.get("minPrice"),
                    "maxPrice":              data.get("maxPrice"),
                    "salesProbability":      data.get("salesProbability"),
                    "salesProbability500":   data.get("salesProbability500"),
                }
        logger.warning(f"GoValue {domain}: HTTP {r.status_code} — {r.text[:100]}")
        return None
    except Exception as e:
        logger.warning(f"GoValue failed for {domain}: {e}")
        return None
