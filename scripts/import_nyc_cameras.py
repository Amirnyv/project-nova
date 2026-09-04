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

    query_candidates = []

    if " @ " in search_location:
        road, cross_street = search_location.split(" @ ", 1)

        query_candidates.append(
            f"{cross_street} & {road}, {record['borough']}, New York, NY"
        )

        query_candidates.append(
            f"{road} & {cross_street}, {record['borough']}, New York, NY"
        )

    else:
        query_candidates.append(
            f"{search_location}, {record['borough']}, New York, NY"
        )

    for query in query_candidates:
        params = urllib.parse.urlencode({
            "q": query,
            "access_token": MAPBOX_TOKEN,
            "bbox": "-74.2591,40.4774,-73.7003,40.9176",
            "limit": 5
        })

        url = (
            "https://api.mapbox.com/search/geocode/v6/forward?"
            + params
        )

        with urllib.request.urlopen(url) as response:
            data = json.load(response)

        features = data.get("features", [])

        for feature in features:
            properties = feature.get("properties", {})
            context = properties.get("context", {})

            locality = (
                context.get("locality", {}).get("name")
                if isinstance(context.get("locality"), dict)
                else None
            )

            district = (
                context.get("district", {}).get("name")
                if isinstance(context.get("district"), dict)
                else None
            )

            expected_borough = record["borough"]

            borough_matches = (
                locality == expected_borough
                or district == f"{expected_borough} County"
            )

            if not borough_matches:
                continue

            matched_text = (
                f"{properties.get('name', '')} "
                f"{properties.get('full_address', '')}"
            ).upper()

            matched_text = (
                matched_text
                .replace(".", "")
                .replace("AVENUE", "AVE")
                .replace("BOULEVARD", "BLVD")
                .replace("STREET", "ST")
                .replace("ROAD", "RD")
            )

            if " @ " in search_location:
                normalized_road = (
    road.upper()
    .replace(".", "")
    .replace("THRUW AY", "THRUWAY")
)

                normalized_road = (
                    road.upper()
                    .replace(".", "")
                    .replace("THRUW AY", "THRUWAY")
                )

                normalized_cross_street = (
                    cross_street.upper()
                    .replace(".", "")
                )

                road_words = [
                    word for word in normalized_road.split()
                    if word not in {
                        "AVE",
                        "BLVD",
                        "ST",
                        "RD",
                        "PKWY",
                        "EXPWY",
                        "THRUWAY",
                        "LN",
                        "DR",
                        "PL"
                    }
                ]

                cross_words = [
                    word for word in normalized_cross_street.split()
                    if word not in {
                        "AVE",
                        "BLVD",
                        "ST",
                        "RD",
                        "PKWY",
                        "EXPWY",
                        "THRUWAY",
                        "LN",
                        "DR",
                        "PL"
                    }
                ]

                road_matches = all(
                    word in matched_text
                    for word in road_words
                )

                cross_matches = all(
                    word in matched_text
                    for word in cross_words
                )

                if not (road_matches and cross_matches):
                    continue

            longitude, latitude = feature["geometry"]["coordinates"]

            return {
                "location": record["location"],
                "borough": record["borough"],
                "violation_count": record["violation_count"],
                "latitude": latitude,
                "longitude": longitude,
                "matched_name": properties.get("name"),
                "matched_address": properties.get("full_address"),
            }

    return None

if __name__ == "__main__":
    locations = fetch_speed_camera_locations(limit=100)

    cameras = []
    rejected = []

    for record in locations:
        cleaned = clean_camera_location(record)
        result = geocode_camera_location(cleaned)

        if result is None:
            rejected.append(cleaned)
            continue

        cameras.append({
            "type": "speed_camera",
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "street": result["location"],
            "borough": result["borough"],
            "source": "nyc_open_data",
            "violation_count": result["violation_count"],
            "confidence": "high",
            "verified": False
        })

    output_data = {
        "updated_at": None,
        "cameras": cameras
    }

    output_path = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "data"
        / "nyc_cameras.json"
    )

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output_data, file, indent=2)

    print(f"Saved {len(cameras)} cameras.")
    print(f"Rejected {len(rejected)} locations.")
    print(f"File: {output_path}")