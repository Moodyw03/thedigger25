from flask import Flask, jsonify, request, make_response, render_template, redirect, url_for
from flask_cors import CORS
import datetime
import logging
from main import main

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    """Render the home page with search form."""
    return render_template('index.html', year=datetime.datetime.now().year)

@app.route("/search")
def search():
    """Handle search requests and display results."""
    artist_name = request.args.get("artist_name", "")
    
    if not artist_name:
        return render_template('index.html', 
                              error="Please enter an artist name",
                              year=datetime.datetime.now().year)
    
    try:
        logger.info(f"Searching for artist: {artist_name}")
        tracks = main(artist_name)
        
        if not tracks:
            return render_template('index.html',
                                  artist_name=artist_name,
                                  error=f"No tracklists found for '{artist_name}'",
                                  year=datetime.datetime.now().year)
        
        return render_template('index.html',
                              artist_name=artist_name,
                              tracks=tracks,
                              year=datetime.datetime.now().year)
    
    except Exception as e:
        logger.error(f"Error searching for {artist_name}: {str(e)}")
        return render_template('index.html',
                              artist_name=artist_name,
                              error=f"An error occurred: {str(e)}",
                              year=datetime.datetime.now().year)

@app.route("/api/list", methods=["GET"])
def fetch_artists():
    """API endpoint for retrieving artist tracklists."""
    try:
        # Access the 'artist_name' query parameter
        artist_name = request.args.get("artist_name", "Ben UFO")
        
        if not artist_name:
            return make_response(
                jsonify({"error": "Artist name is required"}), 400
            )

        logger.info(f"API request for artist: {artist_name}")
        arrays = main(artist_name)

        # Check if arrays is valid or has data
        if not arrays:
            return make_response(
                jsonify({"error": f"No data found for '{artist_name}'"}), 404
            )

        return jsonify(arrays)

    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 400)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return make_response(jsonify({"error": "An unexpected error occurred"}), 500)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('index.html', 
                          error="Page not found. Please use the search form.",
                          year=datetime.datetime.now().year), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('index.html', 
                          error="Server error. Please try again later.",
                          year=datetime.datetime.now().year), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
