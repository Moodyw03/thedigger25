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
from flask import Flask, jsonify, render_template, request, make_response, send_file, redirect, url_for
from flask_cors import CORS
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import time
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default port
PORT = 8080
HOST = "0.0.0.0"

# Create Flask app
app = Flask(__name__)
CORS(app)

# Add a cache dictionary to the app
app.config['MIXES_CACHE'] = {}

# Simple in-memory cache for YouTube video searches
# This will help reduce API calls and improve performance on Vercel
video_id_cache = {}
# Set a cache expiry time (24 hours in seconds)
CACHE_EXPIRY = int(os.environ.get('CACHE_EXPIRY', 86400))

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
        
        # Check cache first
        cache = app.config['MIXES_CACHE']
        cache_key = artist_name.lower()
        
        if cache_key in cache and (datetime.datetime.now() - cache[cache_key]['timestamp']).total_seconds() < 3600:
            # Use cached data if it's less than an hour old
            mixes = cache[cache_key]['data']
            logger.info(f"Using cached data for {artist_name}")
        else:
            # Fetch fresh data
            mixes = main(artist_name)
            
            # Update cache
            cache[cache_key] = {
                'data': mixes,
                'timestamp': datetime.datetime.now()
            }
            logger.info(f"Updated cache for {artist_name}")
        
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
        # Check if we have this query cached already
        if query in video_id_cache:
            logger.info(f"Using cached video ID for query: {query}")
            return jsonify({"videoId": video_id_cache[query]})
        
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
        
        # Cache the result
        video_id_cache[query] = video_id
        
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

@app.route("/download_tracklists_pdf")
def download_tracklists_pdf():
    """Generate and download a PDF with all tracklists for an artist."""
    artist_name = request.args.get("artist_name", "")
    
    if not artist_name:
        return make_response(
            jsonify({"error": "Artist name is required"}), 400
        )
    
    try:
        logger.info(f"Generating PDF for artist: {artist_name}")
        
        # Fetch the tracklists - use cached data if possible
        start_time = datetime.datetime.now()
        
        # Check cache first
        cache = app.config['MIXES_CACHE']
        cache_key = artist_name.lower()
        
        if cache_key in cache and (datetime.datetime.now() - cache[cache_key]['timestamp']).total_seconds() < 3600:
            # Use cached data if it's less than an hour old
            mixes = cache[cache_key]['data']
            logger.info(f"Using cached data for PDF generation - {artist_name}")
        else:
            # Fetch fresh data
            mixes = main(artist_name)
            
            # Update cache
            cache[cache_key] = {
                'data': mixes,
                'timestamp': datetime.datetime.now()
            }
            logger.info(f"Updated cache for PDF generation - {artist_name}")
        
        end_time = datetime.datetime.now()
        process_time = (end_time - start_time).total_seconds()
        logger.info(f"Retrieved {len(mixes)} mixes in {process_time:.2f} seconds")
        
        if not mixes:
            return make_response(
                jsonify({"error": f"No tracklists found for '{artist_name}'"}), 404
            )
        
        # Create a PDF file in memory
        buffer = BytesIO()
        
        # Set up the document with letter size paper
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            title=f"Tracklists for {artist_name}",
            author="The Digger App"
        )
        
        # Styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='MixTitle',
            parent=styles['Heading2'],
            spaceAfter=12
        ))
        
        styles.add(ParagraphStyle(
            name='TrackItem',
            parent=styles['Normal'],
            leftIndent=20,
            spaceAfter=3
        ))
        
        # Create the content for the PDF
        content = []
        
        # Add the title
        title = Paragraph(f"Tracklists for {artist_name}", styles['Title'])
        content.append(title)
        content.append(Spacer(1, 0.25 * inch))
        
        # Add summary stats
        mixes_with_tracklists = sum(1 for mix in mixes if mix.get("has_tracklist", False))
        total_tracks = sum(len(mix.get("tracks", [])) for mix in mixes)
        
        summary = Paragraph(
            f"Found {total_tracks} tracks across {mixes_with_tracklists} mixes with tracklists "
            f"(total of {len(mixes)} mixes)",
            styles['Normal']
        )
        content.append(summary)
        content.append(Spacer(1, 0.25 * inch))
        
        # Generated timestamp
        generated = Paragraph(
            f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}",
            styles['Italic']
        )
        content.append(generated)
        content.append(Spacer(1, 0.5 * inch))
        
        # Add each mix with its tracklist
        for mix in mixes:
            # Mix title and date
            title_text = mix.get("title", "Untitled Mix")
            if mix.get("date"):
                title_text += f" ({mix.get('date')})"
                
            mix_title = Paragraph(title_text, styles['MixTitle'])
            content.append(mix_title)
            
            # Add link to MixesDB
            if mix.get("url"):
                mix_url = Paragraph(
                    f"Source: <a href='{mix.get('url')}'>{mix.get('url')}</a>",
                    styles['Italic']
                )
                content.append(mix_url)
                content.append(Spacer(1, 0.1 * inch))
            
            # Add tracklist if available
            if mix.get("has_tracklist") and mix.get("tracks"):
                # Add each track
                for i, track in enumerate(mix.get("tracks", [])):
                    track_text = f"{i+1}. {track.get('track', '')}"
                    track_item = Paragraph(track_text, styles['TrackItem'])
                    content.append(track_item)
                
                content.append(Spacer(1, 0.25 * inch))
            else:
                no_tracklist = Paragraph("No tracklist available for this mix.", styles['Italic'])
                content.append(no_tracklist)
                content.append(Spacer(1, 0.25 * inch))
            
            # Add a bigger space between mixes
            content.append(Spacer(1, 0.3 * inch))
        
        # Build the PDF document
        doc.build(content)
        
        # Seek to the beginning of the buffer
        buffer.seek(0)
        
        # Create a response with the PDF
        filename = f"tracklists_{artist_name.replace(' ', '_')}.pdf"
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        # Add headers to prevent caching to ensure the download always completes
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating PDF for {artist_name}: {str(e)}")
        return make_response(
            jsonify({"error": f"An error occurred generating the PDF: {str(e)}"}),
            500
        )

@app.route("/direct_pdf_download")
def direct_pdf_download():
    """Generate and download a PDF directly without loading the UI."""
    artist_name = request.args.get("artist_name", "")
    
    if not artist_name:
        return render_template('index.html', 
                              error="Please enter an artist name",
                              year=datetime.datetime.now().year)
    
    try:
        # Show loading page first
        return render_template('pdf_loading.html', 
                              artist_name=artist_name,
                              year=datetime.datetime.now().year)
    except Exception as e:
        logger.error(f"Error processing direct PDF download for {artist_name}: {str(e)}")
        return render_template('index.html',
                              artist_name=artist_name,
                              error=f"An error occurred: {str(e)}",
                              year=datetime.datetime.now().year)

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
    # Configure from environment variables
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("FLASK_PORT", PORT))
    host = os.environ.get("FLASK_HOST", HOST)
    
    # Check environment and show warning if debug mode is enabled
    if debug_mode:
        logger.warning("Debug mode is enabled. This should NOT be used in production!")
    else:
        logger.info("Starting application in production mode")
    
    # Try to open browser
    if "BROWSER" not in os.environ or os.environ.get("BROWSER", "1") == "1":
        url = f"http://localhost:{port}"
        print(f"Opening your browser to {url}")
        # Open browser after a short delay to ensure the server is running
        Timer(1, lambda: webbrowser.open(url)).start()
    else:
        print("Browser auto-open is disabled")
        
    print("Press Ctrl+C to stop the server")
    app.run(debug=debug_mode, host=host, port=port) 