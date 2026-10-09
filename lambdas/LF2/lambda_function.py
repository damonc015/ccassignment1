import base64
import json
import os
import urllib.request

import boto3

sqs = boto3.client("sqs")
ses = boto3.client("ses")
table = boto3.resource("dynamodb").Table("yelp-restaurants")

QUEUE_URL = os.environ["QUEUE_URL"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
OPENSEARCH_AUTH = base64.b64encode(
    f"{os.environ['OPENSEARCH_USER']}:{os.environ['OPENSEARCH_PASSWORD']}".encode()
).decode()
SUGGESTION_COUNT = 3


# Returns random RestaurantIDs for the cuisine from the OpenSearch "restaurants" index.
def search_restaurant_ids(cuisine):
    query = {
        "size": SUGGESTION_COUNT,
        "query": {
            "function_score": {
                "query": {"term": {"Cuisine": cuisine.lower()}},
                "random_score": {},
            }
        },
    }
    request = urllib.request.Request(
        f"{OPENSEARCH_ENDPOINT}/restaurants/_search",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {OPENSEARCH_AUTH}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        hits = json.load(response)["hits"]["hits"]
    return [hit["_source"]["RestaurantID"] for hit in hits]


# Fetches the full restaurant records (name, address, ...) from DynamoDB.
def get_restaurants(restaurant_ids):
    restaurants = []
    for restaurant_id in restaurant_ids:
        item = table.get_item(Key={"businessId": restaurant_id}).get("Item")
        if item:
            restaurants.append(item)
    return restaurants


def format_email(request, restaurants):
    lines = [
        f"Hello! Here are my {request['cuisine'].title()} restaurant suggestions for "
        f"{request['numberOfPeople']} people, for {request['diningTime']}:"
    ]
    for i, restaurant in enumerate(restaurants, 1):
        lines.append(f"{i}. {restaurant['name']}, located at {restaurant['address']}")
    lines.append("Enjoy your meal!")
    return "\n".join(lines)


# Queue worker: pulls a message from Q1, finds suggestions, emails them, then deletes the message.
def lambda_handler(event, context):
    response = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=1)
    messages = response.get("Messages", [])
    if not messages:
        return {"processed": 0}

    message = messages[0]
    request = json.loads(message["Body"])

    restaurants = get_restaurants(search_restaurant_ids(request["cuisine"]))
    if restaurants:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [request["email"]]},
            Message={
                "Subject": {"Data": "Your dining suggestions"},
                "Body": {"Text": {"Data": format_email(request, restaurants)}},
            },
        )

    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=message["ReceiptHandle"])
    return {"processed": 1}