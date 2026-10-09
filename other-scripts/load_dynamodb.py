import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3

TABLE_NAME = "yelp-restaurants"
REGION = "us-east-1"
INPUT = Path(__file__).parent / "data" / "restaurants.json"


def main():
    restaurants = json.loads(INPUT.read_text(), parse_float=Decimal)
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)

    with table.batch_writer(overwrite_by_pkeys=["businessId"]) as batch:
        for restaurant in restaurants:
            restaurant["insertedAtTimestamp"] = datetime.now(timezone.utc).isoformat()
            batch.put_item(Item=restaurant)

    print(f"Loaded {len(restaurants)} restaurants into {TABLE_NAME}")


if __name__ == "__main__":
    main()