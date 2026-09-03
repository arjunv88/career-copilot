import json
import time
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path

import requests

MAJOR_GERMAN_CITIES = {
    "Berlin": (52.5200, 13.4050),
    "Munich": (48.1351, 11.5820),
    "Hamburg": (53.5511, 9.9937),
    "Frankfurt": (50.1109, 8.6821),
    "Stuttgart": (48.7758, 9.1829),
    "Cologne": (50.9375, 6.9603),
    "Dusseldorf": (51.2277, 6.7735),
}

CACHE_FILE = Path(
    "data/geography_cache.json"
)

#"Nuremberg": (49.4521, 11.0767),
#    "Karlsruhe": (49.0069, 8.4037),
#    "Ulm": (48.4011, 9.9876),

def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2,
):

    radius = 6371.0

    dlat = radians(
        lat2 - lat1
    )

    dlon = radians(
        lon2 - lon1
    )

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return radius * c

def find_nearest_major_city(
    latitude: float,
    longitude: float,
):

    nearest_city = None
    nearest_distance = None

    for city, coords in (
        MAJOR_GERMAN_CITIES.items()
    ):

        city_lat, city_lon = coords

        distance = haversine_distance(
            latitude,
            longitude,
            city_lat,
            city_lon,
        )

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):

            nearest_city = city
            nearest_distance = distance

    return (
        nearest_city,
        nearest_distance,
    )
def location_is_allowed(
    distance_km: float | None,
    radius_km: float = 50.0,
):

    if distance_km is None:
        return False

    return (
        distance_km <= radius_km
    )

def load_geography_cache() -> dict:

    if not CACHE_FILE.exists():
        return {}

    try:

        with CACHE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception:

        return {}

def save_geography_cache(
    cache: dict,
):

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with CACHE_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False,
        )    

def geocode_location(
    location: str,
):

    if not location:
        return None

    clean_location = (
        location
        .strip()
        .lower()
    )

    if not clean_location:
        return None

    # Make sure Germany is included
    if "germany" not in clean_location:

        search_query = (
            f"{location}, Germany"
        )

    else:

        search_query = location


    # -----------------------------------
    # 1. Check local cache first
    # -----------------------------------

    cache = load_geography_cache()

    cache_key = (
        search_query
        .strip()
        .lower()
    )


    if cache_key in cache:

        cached_result = (
            cache[
                cache_key
            ]
        )

        return (
            cached_result[
                "latitude"
            ],
            cached_result[
                "longitude"
            ],
        )


    # -----------------------------------
    # 2. Query Nominatim
    # -----------------------------------

    url = (
        "https://nominatim."
        "openstreetmap.org/search"
    )


    headers = {
        "User-Agent": (
            "CareerCopilot/0.5 "
            "(personal job discovery project)"
        )
    }


    params = {
        "q": search_query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "de",
    }


    try:

        # Respect Nominatim public usage limit
        time.sleep(
        1.1
        )

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=20,
        )

        response.raise_for_status()

        results = (
            response.json()
        )


        if not results:

            return None


        latitude = float(
            results[0][
                "lat"
            ]
        )

        longitude = float(
            results[0][
                "lon"
            ]
        )


        # -----------------------------------
        # 3. Save result to cache
        # -----------------------------------

        cache[
            cache_key
        ] = {
            "latitude": latitude,
            "longitude": longitude,
        }


        save_geography_cache(
            cache
        )


        # Nominatim requires a very low request rate.
       # time.sleep(
        #    1.1
        #)


        return (
            latitude,
            longitude,
        )


#    except requests.RequestException:

#        return None
    except requests.RequestException as error:

        print(
            f"Geocoding failed for {location}: {error}"
    )

    return None


def analyse_job_location(
    location: str,
    radius_km: float = 50.0,
):

    coordinates = (
        geocode_location(
            location
        )
    )


    if coordinates is None:

        return {
            "location": location,

            "latitude": None,

            "longitude": None,

            "nearest_major_city": "",

            "distance_km": None,

            "within_radius": False,
        }


    latitude, longitude = (
        coordinates
    )


    (
        nearest_city,
        nearest_distance,
    ) = find_nearest_major_city(
        latitude,
        longitude,
    )


    within_radius = (
        nearest_distance
        <= radius_km
    )


    return {
        "location": location,

        "latitude": latitude,

        "longitude": longitude,

        "nearest_major_city": (
            nearest_city
        ),

        "distance_km": round(
            nearest_distance,
            1,
        ),

        "within_radius": (
            within_radius
        ),
    }
    