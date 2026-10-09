import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
AUTH = (os.environ["OPENSEARCH_USER"], os.environ["OPENSEARCH_PASSWORD"])
INDEX = "restaurants"
INPUT = Path(__file__).parent / "data" / "restaurants.json"


def main():
    restaurants = json.loads(INPUT.read_text())
    lines = []
    for restaurant in restaurants:
        lines.append(json.dumps({"index": {"_index": INDEX, "_id": restaurant["businessId"]}}))
        lines.append(json.dumps({
            "RestaurantID": restaurant["businessId"],
            "Cuisine": restaurant["cuisine"],
            "type": "Restaurant",
        }))

    response = requests.post(
        f"{ENDPOINT}/_bulk",
        auth=AUTH,
        data="\n".join(lines) + "\n",
        headers={"Content-Type": "application/x-ndjson"},
    )
    response.raise_for_status()
    result = response.json()
    if result["errors"]:
        raise SystemExit(f"Bulk indexing had errors: {result['items'][:3]}")

    print(f"Indexed {len(result['items'])} restaurants into {INDEX}")


if __name__ == "__main__":
    main()