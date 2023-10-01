from flask import Flask, jsonify, request, make_response
from flask_cors import CORS

from main import main


app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    return "Welcome to the digger! \nNow on vercel"


@app.route("/api/list", methods=["GET"])
def fetch_artists():
    try:
        # Access the 'artist_name' query parameter
        artist_name = request.args.get("artist_name", "Ben UFO")

        # Validate artist_name if necessary
        # e.g., check if it's not empty, has valid characters, etc.

        arrays = main(artist_name)

        # Check if arrays is valid or has data
        if not arrays:
            return make_response(
                jsonify({"error": "No data found for the given " + artist_name}), 404
            )

        return jsonify(arrays)

    except ValueError as e:  # Example error
        return make_response(jsonify({"error": str(e)}), 400)

    except Exception as e:
        # Log the error for debugging
        # print(e)  # Or use logging module for production
        return make_response(jsonify({"error": "An unexpected error occurred"}), 500)
