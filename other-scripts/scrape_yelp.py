import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["YELP_API_KEY"]
SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
CUISINES = ["chinese", "italian", "japanese", "mexican", "indian", "thai"]
LOCATION = "Manhattan, NY"
PAGE_SIZE = 50
PER_CUISINE = 200
OUTPUT = Path(__file__).parent / "data" / "restaurants.json"


def search(cuisine, offset):
    response = requests.get(
        SEARCH_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        params={
            "term": f"{cuisine} restaurants",
            "location": LOCATION,
            "limit": PAGE_SIZE,
            "offset": offset,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("businesses", [])


def to_record(business, cuisine):
    location = business.get("location") or {}
    coordinates = business.get("coordinates") or {}
    return {
        "businessId": business["id"],
        "name": business.get("name"),
        "cuisine": cuisine,
        "address": ", ".join(location.get("display_address") or []),
        "zipCode": location.get("zip_code"),
        "coordinates": {
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
        },
        "numberOfReviews": business.get("review_count"),
        "rating": business.get("rating"),
    }


def main():
    restaurants = {}
    for cuisine in CUISINES:
        added = 0
        for offset in range(0, PER_CUISINE, PAGE_SIZE):
            businesses = search(cuisine, offset)
            if not businesses:
                break
            for business in businesses:
                if business["id"] not in restaurants:
                    restaurants[business["id"]] = to_record(business, cuisine)
                    added += 1
            time.sleep(0.5)
        print(f"{cuisine}: {added} new restaurants")

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(list(restaurants.values()), indent=2))
    print(f"Saved {len(restaurants)} restaurants to {OUTPUT}")


if __name__ == "__main__":
    main()