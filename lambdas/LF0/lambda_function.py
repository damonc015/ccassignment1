import os
import boto3

lex = boto3.client("lexv2-runtime")

BOT_ID = os.environ["BOT_ID"]
BOT_ALIAS_ID = os.environ.get("BOT_ALIAS_ID", "TSTALIASID")
LOCALE_ID = os.environ.get("LOCALE_ID", "en_US")


def build_response(texts):
    return {"messages": [{"type": "unstructured", "unstructured": {"text": t}} for t in texts]}


def lambda_handler(event, context):
    try:
        message = event["messages"][0]["unstructured"]
        text = message["text"]
    except (KeyError, IndexError, TypeError):
        return build_response(["Sorry, I didn't receive a message."])

    lex_response = lex.recognize_text(
        botId=BOT_ID,
        botAliasId=BOT_ALIAS_ID,
        localeId=LOCALE_ID,
        sessionId=message.get("id") or "default-session",
        text=text,
    )
    texts = [m["content"] for m in lex_response.get("messages", []) if m.get("content")]
    return build_response(texts or ["Sorry, could you rephrase that?"])
