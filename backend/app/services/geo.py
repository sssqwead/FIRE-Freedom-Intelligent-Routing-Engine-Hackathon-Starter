from __future__ import annotations

import json
import logging
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import BusinessUnit, GeoCache, RRState, Ticket

logger = logging.getLogger(__name__)

# Offline fallback for stable geo behavior (if API unavailable/rate-limited).
KZ_CITY_COORDS: dict[str, tuple[float, float]] = {
    "актау": (43.6532, 51.1975),
    "актобе": (50.2839, 57.1669),
    "алматы": (43.2389, 76.8897),
    "астана": (51.1694, 71.4491),
    "атырау": (47.0945, 51.9238),
    "караганда": (49.8028, 73.0877),
    "кокшетау": (53.2833, 69.3833),
    "костанай": (53.2144, 63.6246),
    "кызылорда": (44.8488, 65.4823),
    "павлодар": (52.2871, 76.9674),
    "петропавловск": (54.8728, 69.1430),
    "тараз": (42.9, 71.3667),
    "уральск": (51.2278, 51.3865),
    "усть-каменогорск": (49.9714, 82.6059),
    "шымкент": (42.3170, 69.5901),
}

def is_kz(country: str) -> bool:
    c = (country or "").strip().lower()
    return c in ["kz", "kazakhstan", "қазақстан", "казахстан"]

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _pick_city_from_text(text: str) -> tuple[float, float] | None:
    t = _norm(text)
    if not t:
        return None
    for city, coords in KZ_CITY_COORDS.items():
        if city in t:
            return coords
    return None

def _save_cache(db: Session, query: str, lat: float, lon: float, source: str) -> None:
    key = _norm(query)
    if not key:
        return
    row = db.query(GeoCache).filter(GeoCache.query == key).one_or_none()
    if row is None:
        row = GeoCache(query=key, lat=lat, lon=lon, source=source)
    else:
        row.lat = lat
        row.lon = lon
        row.source = source
    db.add(row)
    db.commit()

def _geocode_nominatim(query: str) -> tuple[float, float] | None:
    if not settings.GEOCODER_ENABLED:
        return None

    params = urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 0,
            "accept-language": settings.GEOCODER_LANG,
        }
    )
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = Request(
        url,
        headers={
            "User-Agent": settings.GEOCODER_USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=settings.GEOCODER_TIMEOUT_SEC) as resp:  
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload:
            return None
        first = payload[0]
        return float(first["lat"]), float(first["lon"])
    except Exception as exc:
        logger.warning("nominatim geocode failed for '%s': %s", query, exc)
        return None

def geocode_cached(db: Session, query: str) -> tuple[float, float, str] | None:
    key = _norm(query)
    if not key:
        return None

    cached = db.query(GeoCache).filter(GeoCache.query == key).one_or_none()
    if cached is not None:
        return cached.lat, cached.lon, f"cache:{cached.source}"

    api_res = _geocode_nominatim(query)
    if api_res is not None:
        lat, lon = api_res
        _save_cache(db, key, lat, lon, "nominatim")
        return lat, lon, "nominatim"

    city_res = _pick_city_from_text(query)
    if city_res is not None:
        lat, lon = city_res
        _save_cache(db, key, lat, lon, "city_fallback")
        return lat, lon, "city_fallback"

    return None

def geocode_ticket(db: Session, ticket: Ticket) -> tuple[float | None, float | None, str]:
    country = (ticket.country or "").strip()
    city = (ticket.city or "").strip()
    region = (ticket.region or "").strip()
    street = (ticket.street or "").strip()
    house = (ticket.house or "").strip()

    if not is_kz(country):
        return None, None, "non_kz"

    if not any([city, region, street, house]):
        return None, None, "empty_address"

    address = ", ".join([p for p in [house, street, city, region, "Казахстан"] if p])
    res = geocode_cached(db, address)
    if res is not None:
        lat, lon, source = res
        return lat, lon, source
    return None, None, "unresolved"

def choose_fallback_office_50_50(db: Session) -> str:
    
    key = "fallback:astana_almaty"
    st = db.query(RRState).filter(RRState.key == key).one_or_none()
    if st is None:
        st = RRState(key=key, last_pair="Астана,Алматы", toggle=0)
        db.add(st)
        db.commit()
        return "Астана"
    office = "Астана" if st.toggle == 0 else "Алматы"
    st.toggle = 1 - st.toggle
    db.add(st)
    db.commit()
    return office

def map_office_by_city(db: Session, city: str) -> str | None:
    city_l = (city or "").strip().lower()
    if not city_l:
        return None
    bus = db.query(BusinessUnit).all()
    for b in bus:
        blob = f"{b.office} {b.address}".lower()
        if city_l in blob:
            return b.office
    return None

def _office_coords(db: Session, bu: BusinessUnit) -> tuple[float, float] | None:
    query = ", ".join([p for p in [bu.office, bu.address, "Казахстан"] if p])
    res = geocode_cached(db, query)
    if res is None:
        return None
    lat, lon, _ = res
    return lat, lon

def _nearest_office_by_coords(db: Session, lat: float, lon: float) -> str | None:
    nearest_office: str | None = None
    nearest_km: float | None = None
    for bu in db.query(BusinessUnit).all():
        coords = _office_coords(db, bu)
        if coords is None:
            continue
        bu_lat, bu_lon = coords
        dist = _haversine_km(lat, lon, bu_lat, bu_lon)
        if nearest_km is None or dist < nearest_km:
            nearest_km = dist
            nearest_office = bu.office
    return nearest_office

def choose_office(
    db: Session,
    country: str,
    city: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[str, str]:
    
    if (not is_kz(country)) or (not city.strip()):
        office = choose_fallback_office_50_50(db)
        return office, "fallback_50_50_astana_almaty"

    if lat is not None and lon is not None:
        nearest = _nearest_office_by_coords(db, lat, lon)
        if nearest:
            return nearest, "nearest_office_by_geocode"

    mapped = map_office_by_city(db, city)
    if mapped:
        return mapped, "matched_city_to_business_unit"
    
    office = choose_fallback_office_50_50(db)
    return office, "city_not_mapped_fallback_50_50"
