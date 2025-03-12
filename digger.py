#!/usr/bin/env python3
"""
The Digger - A tool for finding DJ trackslists from MixesDB
"""
import os
import sys
import datetime
import logging
import webbrowser
import urllib.parse
import json
import requests
from threading import Timer
from flask import Flask, jsonify, render_template, request, make_response
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default port
PORT = 8080
HOST = "0.0.0.0"

# Create Flask app
app = Flask(__name__)
CORS(app)

# Add URL encode filter for Jinja2 templates
@app.template_filter('urlencode')
def urlencode_filter(s):
    """URL encode a string."""
    if isinstance(s, str):
        s = s.encode('utf-8')
    return urllib.parse.quote_plus(s)

# Import main functionality here to avoid circular imports
from main import main

@app.route("/")
def index():
    """Render the home page with search form."""
    return render_template('index.html', year=datetime.datetime.now().year)

@app.route("/debug")
def debug():
    """Render the debug page for troubleshooting."""
    return render_template('debug.html')

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
        mixes = main(artist_name)
        
        if not mixes:
            return render_template('index.html',
                                  artist_name=artist_name,
                                  error=f"No tracklists found for '{artist_name}'",
                                  year=datetime.datetime.now().year)
        
        return render_template('index.html',
                              artist_name=artist_name,
                              tracks=mixes,
                              year=datetime.datetime.now().year)
    
    except Exception as e:
        logger.error(f"Error searching for {artist_name}: {str(e)}")
        return render_template('index.html',
                              artist_name=artist_name,
                              error=f"An error occurred: {str(e)}",
                              year=datetime.datetime.now().year)

@app.route("/search_video")
def search_video():
    """Search for a video on YouTube and return the video ID."""
    query = request.args.get("query", "")
    
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    try:
        # We'll use a simple approach to extract video ID from YouTube search results
        # This doesn't require an API key but is a bit of a hack
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        logger.info(f"Searching YouTube for: {query}")
        
        # Use the retry logic from main.py here
        import main
        response = main.fetch_with_retry(search_url)
        
        # Extract video ID from the response
        # This is a simple approach that may break if YouTube changes their page structure
        html = response.text
        logger.info(f"Received HTML response of length: {len(html)}")
        
        # Look for videoId in the response
        video_id = None
        
        # Try multiple patterns to find video ID
        patterns = [
            '"videoId":"', 
            'watch?v=',
            '/embed/',
            '/v/'
        ]
        
        for pattern in patterns:
            start_idx = html.find(pattern)
            if start_idx != -1:
                start_idx += len(pattern)
                
                # Determine end of video ID based on which pattern was found
                if pattern == '"videoId":"':
                    end_idx = html.find('"', start_idx)
                else:
                    # For URL patterns, look for ending delimiters
                    end_idx = next((html.find(c, start_idx) for c in ['"', '&', '#', '?', ' '] 
                                   if html.find(c, start_idx) != -1), len(html))
                
                if end_idx != -1:
                    video_id = html[start_idx:end_idx]
                    logger.info(f"Found video ID using pattern '{pattern}': {video_id}")
                    break
        
        if not video_id:
            # Try one more approach - look for any watch?v= format
            import re
            match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
            if match:
                video_id = match.group(1)
                logger.info(f"Found video ID using regex: {video_id}")
        
        if not video_id:
            logger.warning(f"No video ID found for query: {query}")
            return jsonify({"error": "No video found"}), 404
            
        # Basic validation - YouTube IDs are usually 11 characters
        if len(video_id) != 11:
            logger.warning(f"Found invalid video ID (length != 11): {video_id}")
            # Try to extract just the 11 character ID if we found something longer
            if len(video_id) > 11:
                video_id = video_id[:11]
                logger.info(f"Truncated to 11 characters: {video_id}")
        
        return jsonify({"videoId": video_id})
        
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

def open_browser():
    """Open the browser after a short delay."""
    webbrowser.open(f"http://localhost:{PORT}")

def main_runner():
    """Main function to run the application."""
    # Open browser after a short delay
    Timer(1.5, open_browser).start()
    
    # Start the Flask app
    app.run(debug=True, host=HOST, port=PORT)

if __name__ == "__main__":
    print(f"Starting The Digger application...")
    print(f"Opening your browser to http://localhost:{PORT}")
    print(f"Press Ctrl+C to stop the server")
    
    # Run the app
    main_runner() 