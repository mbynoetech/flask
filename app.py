
import os
import re
import requests

from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# -----------------------------
# RAPIDAPI CONFIGURATION
# -----------------------------

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "fa1c43979dmsh0f4c5307cba620cp13b9a0jsn291d9a9db6dc").strip()
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "multilingual-ai-zodiac-customized-horoscopes-for-all-signs.p.rapidapi.com").strip()

API_URL = f"https://{RAPIDAPI_HOST}/horoscope-all.php"

# Change this if your provider uses another parameter.
SIGN_PARAMETER = os.getenv("SIGN_PARAMETER", "sign")

VALID_SIGNS = {
    "aries", "taurus", "gemini", "cancer",
    "leo", "virgo", "libra", "scorpio",
    "sagittarius", "capricorn", "aquarius", "pisces"
}

# Fields that are likely to contain horoscope predictions.
PREFERRED_FIELDS = {
    "horoscope",
    "daily_horoscope",
    "today_horoscope",
    "prediction",
    "daily_prediction",
    "description",
    "message",
    "content",
    "text"
}

# Fields that should never be treated as predictions.
IGNORED_FIELDS = {
    "date", "datetime", "timestamp",
    "day", "month", "months", "year",
    "time", "sign", "zodiac", "id",
    "status", "created_at", "updated_at",
    "weekly", "weekly_horoscope",
    "monthly", "monthly_horoscope",
    "yearly", "yearly_horoscope"
}


# -----------------------------
# DATE DETECTION
# -----------------------------

def is_date_only(value):

    text = str(value).strip()

    patterns = [
        r"^\d{4}-\d{1,2}-\d{1,2}$",
        r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$",
        r"^\d{4}$",
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$"
    ]

    return any(
        re.fullmatch(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


# -----------------------------
# FIND HOROSCOPE PREDICTION
# -----------------------------

def find_prediction(data, depth=0):

    if depth > 10 or data is None:
        return None

    if isinstance(data, str):

        text = data.strip()

        if len(text) >= 40 and not is_date_only(text):
            return text

        return None

    if isinstance(data, list):

        for item in data:

            result = find_prediction(item, depth + 1)

            if result:
                return result

        return None

    if not isinstance(data, dict):
        return None

    # Search preferred prediction fields first.
    for field in PREFERRED_FIELDS:

        for key, value in data.items():

            if key.lower() != field:
                continue

            if isinstance(value, str):

                text = value.strip()

                if len(text) >= 40 and not is_date_only(text):
                    return text

            elif isinstance(value, (dict, list)):

                result = find_prediction(value, depth + 1)

                if result:
                    return result

    # Search other nested fields.
    for key, value in data.items():

        normalized_key = key.lower()

        if normalized_key in IGNORED_FIELDS:
            continue

        if (
            "month" in normalized_key
            or "year" in normalized_key
            or "weekly" in normalized_key
        ):
            continue

        if isinstance(value, str):

            text = value.strip()

            if len(text) >= 40 and not is_date_only(text):
                return text

        elif isinstance(value, (dict, list)):

            result = find_prediction(value, depth + 1)

            if result:
                return result

    return None


# -----------------------------
# HOMEPAGE
# -----------------------------

@app.route("/")
def home():

    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "index.html"
    )


# -----------------------------
# HOROSCOPE API
# -----------------------------

@app.route("/horoscope", methods=["GET"])
def horoscope():

    sign = request.args.get("sign", "").strip().lower()

    if sign not in VALID_SIGNS:

        return jsonify({
            "error": "Please select a valid zodiac sign."
        }), 400

    if not RAPIDAPI_KEY or not RAPIDAPI_HOST:

        return jsonify({
            "error": "RapidAPI credentials are missing. Check your .env file."
        }), 500

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    params = {
        SIGN_PARAMETER: sign
    }

    try:

        response = requests.get(
            API_URL,
            headers=headers,
            params=params,
            timeout=25
        )

        if response.status_code != 200:

            return jsonify({
                "error": "RapidAPI request failed.",
                "api_status": response.status_code,
                "details": response.text[:1000]
            }), 502

        try:
            data = response.json()

        except ValueError:

            return jsonify({
                "error": "RapidAPI did not return valid JSON."
            }), 502

        prediction = find_prediction(data)

        if not prediction:

            app.logger.warning(
                "No horoscope prediction found for %s. API response: %s",
                sign,
                str(data)[:3000]
            )

            return jsonify({
                "error": "The API returned data, but no recognizable horoscope prediction was found.",
                "message": "Check the RapidAPI response structure and prediction field.",
                "api_response": data
            }), 502

        return jsonify({
            "success": True,
            "sign": sign,
            "prediction": prediction
        }), 200

    except requests.exceptions.Timeout:

        return jsonify({
            "error": "RapidAPI request timed out. Please try again."
        }), 504

    except requests.exceptions.RequestException as error:

        app.logger.exception("RapidAPI connection error")

        return jsonify({
            "error": "Could not connect to RapidAPI."
        }), 502


# -----------------------------
# START SERVER
# -----------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
