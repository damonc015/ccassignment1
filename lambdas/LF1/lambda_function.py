import json
import os

import boto3

sqs = boto3.client("sqs")
state_table = boto3.resource("dynamodb").Table("user-state")
QUEUE_URL = os.environ["QUEUE_URL"]

SUPPORTED_LOCATION = "manhattan"
SUPPORTED_CUISINES = {"chinese", "italian", "japanese", "mexican", "indian", "thai"}
SAME_AS_LAST_SLOT = "SameAsLast"


# Returns a slot's value (Lex's interpreted value, falling back to what the user typed), or None if the slot is empty.
def get_slot(slots, name):
    slot = (slots or {}).get(name)
    if not slot or not slot.get("value"):
        return None
    value = slot["value"]
    return value.get("interpretedValue") or value.get("originalValue")


# Tells Lex the intent is finished and replies to the user with the given message.
def close(intent, message):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                "name": intent["name"],
                "slots": intent.get("slots") or {},
                "state": "Fulfilled",
            },
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


# Hands control back to Lex so it prompts for the next empty slot, or moves on to fulfillment once all slots are filled.
def delegate(intent):
    return {
        "sessionState": {
            "dialogAction": {"type": "Delegate"},
            "intent": {
                "name": intent["name"],
                "slots": intent.get("slots") or {},
                "state": "InProgress",
            },
        }
    }


# Clears the given slot and tells Lex to ask the user for it again with a custom message.
def elicit_slot(intent, slot_name, message):
    slots = dict(intent.get("slots") or {})
    slots[slot_name] = None
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": {
                "name": intent["name"],
                "slots": slots,
                "state": "InProgress",
            },
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


# Returns the user's last search (saved by LF2) if it was for the same location and cuisine, otherwise None.
def get_last_search(user_id, location, cuisine):
    item = state_table.get_item(Key={"userId": user_id}).get("Item")
    if item and item["location"].lower() == location.lower() and item["cuisine"].lower() == cuisine.lower():
        return item
    return None


# Handles DiningSuggestionsIntent: validates the location during the conversation, then once every slot is filled,
# pushes the request to the SQS queue (Q1) and confirms to the user that suggestions will be emailed.
def handle_dining(event):
    intent = event["sessionState"]["intent"]
    slots = intent.get("slots") or {}

    location = get_slot(slots, "Location")
    if location and location.lower() != SUPPORTED_LOCATION:
        return elicit_slot(
            intent,
            "Location",
            f"Sorry, I can't fulfill requests for {location}. Please enter a valid location.",
        )

    cuisine = get_slot(slots, "Cuisine")
    if cuisine and cuisine.lower() not in SUPPORTED_CUISINES:
        return elicit_slot(
            intent,
            "Cuisine",
            f"Sorry, I don't have suggestions for {cuisine}. "
            "Try Chinese, Italian, Japanese, Mexican, Indian, or Thai.",
        )

    same_as_last = get_slot(slots, SAME_AS_LAST_SLOT)
    if location and cuisine and same_as_last in (None, "Yes"):
        last_search = get_last_search(event["sessionId"], location, cuisine)
        if last_search and same_as_last is None:
            return elicit_slot(
                intent,
                SAME_AS_LAST_SLOT,
                f"Last time you searched for {cuisine} food in {location}. "
                "Would you like the same recommendations as last time?",
            )
        if last_search:
            suggestions = " ".join(
                f"{i}. {restaurant}." for i, restaurant in enumerate(last_search["recommendations"], 1)
            )
            return close(intent, f"Here are your suggestions from last time: {suggestions} Enjoy your meal!")

    if event["invocationSource"] == "DialogCodeHook":
        return delegate(intent)

    request = {
        "userId": event["sessionId"],
        "location": location,
        "cuisine": cuisine,
        "diningTime": get_slot(slots, "DiningTime"),
        "numberOfPeople": get_slot(slots, "NumberOfPeople"),
        "email": get_slot(slots, "Email"),
    }
    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(request))

    return close(
        intent,
        f"You're all set. I've received your request and will email my suggestions to {request['email']} shortly!",
    )


# Entry point Lex calls on each turn: routes the request to the right handler based on the intent name.
def lambda_handler(event, context):
    intent = event["sessionState"]["intent"]
    name = intent["name"]

    if name == "GreetingIntent":
        return close(intent, "Hi there, how can I help?")
    if name == "ThankYouIntent":
        return close(intent, "You're welcome.")
    if name == "DiningSuggestionsIntent":
        return handle_dining(event)
    return delegate(intent)
