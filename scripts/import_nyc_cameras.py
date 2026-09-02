from pathlib import Path
import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv


NYC_CAMERA_DATASET = "pvqr-7yc4"

OUTPUT_FILE = (
    Path(__file__).resolve().parent.parent
    / "static"
    / "data"
    / "nyc_cameras.json"
)

def fetch_speed_camera_locations(limit=20):
    params = urllib.parse.urlencode({
        "$select": (
            "street_name,"
            "intersecting_street,"
            "violation_county,"
            "count(*) as violation_count"
        ),
        "$where": "violation_code=36",
        "$group": (
            "street_name,"
            "intersecting_street,"
            "violation_county"
        ),
        "$order": "violation_count DESC",
        "$limit": limit
    })

    url = (
        "https://data.cityofnewyork.us/resource/"
        f"{NYC_CAMERA_DATASET}.json?"
        + params
    )

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    return data

COUNTY_NAMES = {
    "MN": "Manhattan",
    "NY": "Manhattan",
    "BK": "Brooklyn",
    "K": "Brooklyn",
    "QN": "Queens",
    "Q": "Queens",
    "BX": "Bronx",
    "ST": "Staten Island",
    "R": "Staten Island"
}

load_dotenv()

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")


def repair_split_intersection(record):
    street = record.get(
        "street_name",
        ""
    ).strip()

    intersecting = record.get(
        "intersecting_street",
        ""
    ).strip()

    if " @ " in street:
        road, fragment = street.split(" @ ", 1)

        if fragment:
            return f"{road} @ {fragment}{intersecting}"

    return f"{street} {intersecting}"


def clean_camera_location(record):
    county = record.get(
        "violation_county",
        ""
    ).strip()

    borough = COUNTY_NAMES.get(
        county,
        county
    )

    location = repair_split_intersection(record)
    location = " ".join(location.split())

    return {
        "location": location,
        "borough": borough,
        "violation_count": int(
            record.get(
                "violation_count",
                0
            )
        )
    }


def geocode_camera_location(record):
    if not MAPBOX_TOKEN:
        return None

    search_location = record["location"]

    if search_location.startswith(("NB ", "SB ", "EB ", "WB ")):
        search_location = search_location[3:]

    search_location = search_location.replace(" @ ", " and ")

    query = ", ".join([
        search_location,
        record["borough"],
        "New York, NY"
    ])

    params = urllib.parse.urlencode({
        "q": query,
        "access_token": MAPBOX_TOKEN,
        "bbox": "-74.2591,40.4774,-73.7003,40.9176",
        "limit": 1
    })

    url = (
        "https://api.mapbox.com/search/geocode/v6/forward?"
        + params
    )

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    features = data.get("features", [])

    if not features:
        return None

    longitude, latitude = features[0]["geometry"]["coordinates"]

    return {
        "location": record["location"],
        "borough": record["borough"],
        "violation_count": record["violation_count"],
        "latitude": latitude,
        "longitude": longitude
    }

if __name__ == "__main__":
    locations = fetch_speed_camera_locations(limit=5)

    cleaned = [
        clean_camera_location(record)
        for record in locations
    ]

    geocoded = [
        result
        for record in cleaned
        if (result := geocode_camera_location(record)) is not None
    ]

    print(
        json.dumps(
            geocoded,
            indent=2
        )
    )
