from flask import Flask, jsonify, request, make_response, render_template, redirect, url_for
from flask_cors import CORS
import datetime
import logging
import os
import time
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from main import main
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

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
        
        # Use cached data if it's available
        cache = getattr(app, 'mixes_cache', {})
        cache_key = artist_name.lower()
        
        if cache_key in cache and (datetime.datetime.now() - cache[cache_key]['timestamp']).total_seconds() < 3600:
            # Use cached data if it's less than an hour old
            mixes = cache[cache_key]['data']
            logger.info(f"Using cached data for PDF generation - {artist_name}")
        else:
            # Fetch fresh data
            mixes = main(artist_name)
            
            # Add to cache
            if not hasattr(app, 'mixes_cache'):
                app.mixes_cache = {}
            app.mixes_cache[cache_key] = {
                'data': mixes,
                'timestamp': datetime.datetime.now()
            }
            logger.info(f"Updated cache for PDF generation - {artist_name}")
        
        if not mixes:
            return make_response(
                jsonify({"error": f"No tracklists found for '{artist_name}'"}), 404
            )
        
        # Generate the PDF
        pdf_data = generate_pdf(artist_name, mixes)
        
        # Create a response with the PDF
        filename = f"tracklists_{artist_name.replace(' ', '_')}.pdf"
        response = make_response(pdf_data)
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

def generate_pdf(artist_name, mixes):
    """Generate a PDF document with all tracklists for an artist."""
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
    
    # Get the value from the buffer
    buffer.seek(0)
    return buffer.getvalue()

if __name__ == "__main__":
    # Get environment variables
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 8080))
    
    # Check environment and show warning if debug mode is enabled
    if debug_mode:
        logger.warning("Debug mode is enabled. This should NOT be used in production!")
    else:
        logger.info("Starting application in production mode")
    
    app.run(debug=debug_mode, host=host, port=port)
