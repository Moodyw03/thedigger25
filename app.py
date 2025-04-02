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
# Import the main scraping function
import main as scraper # Renamed to avoid confusion with main module name
from dotenv import load_dotenv

# RQ imports
from redis import from_url as redis_from_url
from rq import Queue

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- RQ and Redis Setup ---
# Get Redis URL from environment (provided by Railway)
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
try:
    redis_conn = redis_from_url(redis_url)
    # Test connection
    redis_conn.ping()
    logger.info(f"Successfully connected to Redis at {redis_url}")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    # If Redis isn't available, the app can still render the basic page,
    # but background tasks won't work.
    redis_conn = None

if redis_conn:
    # Use the 'default' queue
    q = Queue(connection=redis_conn)
    logger.info("RQ Queue initialized.")
else:
    q = None
    logger.warning("RQ Queue not initialized due to Redis connection failure.")
# ------

@app.route("/")
def index():
    """Render the home page with search form."""
    return render_template('index.html', year=datetime.datetime.now().year)

@app.route("/search", methods=['POST']) # Changed to POST for clarity
def start_search_job():
    """Enqueue a search job and return the job ID."""
    artist_name = request.form.get("artist_name", "")
    
    if not artist_name:
        # Return an error if no artist name provided
        return jsonify({"error": "Artist name is required"}), 400
    
    if q is None:
        logger.error("Cannot enqueue job: RQ Queue not available (Redis connection failed).")
        return jsonify({"error": "Background task queue is not available"}), 503 # Service Unavailable

    try:
        logger.info(f"Enqueuing search job for artist: {artist_name}")
        
        # Enqueue the scraper.main function with the artist name.
        # Pass the function itself, or its string path if needed.
        # Use job_timeout to prevent jobs from running indefinitely
        job = q.enqueue('main.main', artist_name, job_timeout=900) # Timeout after 15 mins
        
        logger.info(f"Job enqueued with ID: {job.id}")
        # Return the job ID to the client
        return jsonify({"job_id": job.id})
    
    except Exception as e:
        logger.error(f"Error enqueuing job for {artist_name}: {str(e)}")
        return jsonify({"error": f"An error occurred while starting the search: {str(e)}"}), 500

@app.route("/job/<job_id>/status")
def get_job_status(job_id):
    """Check the status of a background job."""
    if q is None:
         return jsonify({"error": "Background task queue is not available"}), 503
    try:
        job = q.fetch_job(job_id)
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch job status"}), 500

    if job is None:
        return jsonify({"status": "not_found"}), 404

    response = {
        "job_id": job.id,
        "status": job.get_status(), # Returns 'queued', 'started', 'finished', 'failed', etc.
        "meta": job.meta # Any metadata associated with the job
    }
    
    if job.is_failed:
        # Optionally include error details (be careful about exposing too much)
        response["error_message"] = job.exc_info.strip().split('\n')[-1] if job.exc_info else "Unknown error"
        logger.warning(f"Job {job_id} failed: {response['error_message']}")

    return jsonify(response)

@app.route("/job/<job_id>/result")
def get_job_result(job_id):
    """Fetch the result of a completed background job."""
    if q is None:
         return jsonify({"error": "Background task queue is not available"}), 503
    try:
        job = q.fetch_job(job_id)
    except Exception as e:
        logger.error(f"Error fetching job {job_id} result: {e}")
        return jsonify({"error": "Failed to fetch job result"}), 500

    if job is None:
        return jsonify({"error": "Job not found"}), 404

    if not job.is_finished:
        return jsonify({"error": "Job has not finished yet", "status": job.get_status()}), 202 # Accepted, but not complete

    if job.result is None and not job.is_failed:
        # Handle cases where job finished but result is None (might indicate an issue in the task)
        logger.warning(f"Job {job_id} finished but result is None.")
        return jsonify({"error": "Job completed but returned no result.", "status": job.get_status()}), 500
        
    if job.is_failed:
        error_message = job.exc_info.strip().split('\n')[-1] if job.exc_info else "Unknown error"
        return jsonify({"error": f"Job failed: {error_message}", "status": job.get_status()}), 500

    # Return the actual result from the job
    return jsonify({"status": "finished", "data": job.result})


# --- Keep other routes like API, PDF generation, error handlers ---
# Note: PDF generation might also need to be backgrounded if it becomes slow

# Original /search route is removed as it's replaced by the job submission logic.
# Original /api/list might still be useful if you want synchronous access,
# but it will suffer from the same timeout issues for long requests.
# Consider creating an async version or removing it if /search covers the use case.
@app.route("/api/list", methods=["GET"])
def fetch_artists():
    # THIS ROUTE IS STILL SYNCHRONOUS AND WILL TIMEOUT FOR LONG REQUESTS
    # Consider removing or adapting to use the job queue if needed.
    logger.warning("Synchronous /api/list called - may timeout for long requests.")
    try:
        artist_name = request.args.get("artist_name", "")
        if not artist_name:
            return make_response(jsonify({"error": "Artist name is required"}), 400)

        logger.info(f"API request for artist: {artist_name}")
        # Call the scraper directly (potential timeout)
        arrays = scraper.main(artist_name)

        if not arrays:
            return make_response(jsonify({"error": f"No data found for '{artist_name}'"}), 404)

        return jsonify(arrays)
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 400)
    except Exception as e:
        logger.error(f"Unexpected error in /api/list: {str(e)}")
        return make_response(jsonify({"error": "An unexpected error occurred"}), 500)

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    # Check if the request wants JSON
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'Not Found'})
        response.status_code = 404
        return response
    # Otherwise, return HTML error page
    return render_template('index.html', 
                          error="Page not found. Please use the search form.",
                          year=datetime.datetime.now().year), 404

@app.errorhandler(500)
def server_error(e):
    # Check if the request wants JSON
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'Internal Server Error'})
        response.status_code = 500
        return response
    # Otherwise, return HTML error page
    return render_template('index.html', 
                          error="Server error. Please try again later.",
                          year=datetime.datetime.now().year), 500

# --- PDF Generation (Remains synchronous for now) ---
@app.route("/download_tracklists_pdf")
def download_tracklists_pdf():
    # THIS ROUTE IS SYNCHRONOUS AND MAY TIMEOUT FOR LONG-RUNNING SCRAPES
    artist_name = request.args.get("artist_name", "")
    if not artist_name:
        return make_response(jsonify({"error": "Artist name is required"}), 400)
    
    try:
        logger.info(f"Generating PDF for artist: {artist_name}")
        # Fetch fresh data (potential timeout)
        mixes = scraper.main(artist_name)
        
        if not mixes:
            return make_response(jsonify({"error": f"No tracklists found for '{artist_name}'"}), 404)
        
        pdf_data = generate_pdf(artist_name, mixes)
        
        filename = f"tracklists_{artist_name.replace(' ', '_')}.pdf"
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate' 
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        logger.error(f"Error generating PDF for {artist_name}: {str(e)}")
        return make_response(jsonify({"error": f"An error occurred generating the PDF: {str(e)}"}), 500)

@app.route("/direct_pdf_download") # This also remains synchronous
def direct_pdf_download():
    artist_name = request.args.get("artist_name", "")
    if not artist_name:
        return render_template('index.html', error="Please enter an artist name", year=datetime.datetime.now().year)
    try:
        # Show loading page first, but the actual PDF generation will happen synchronously
        # in download_tracklists_pdf if called from frontend
        return render_template('pdf_loading.html', artist_name=artist_name, year=datetime.datetime.now().year)
    except Exception as e:
        logger.error(f"Error processing direct PDF download for {artist_name}: {str(e)}")
        return render_template('index.html', artist_name=artist_name, error=f"An error occurred: {str(e)}", year=datetime.datetime.now().year)

def generate_pdf(artist_name, mixes):
    """Generate a PDF document with all tracklists for an artist."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"Tracklists for {artist_name}", author="The Digger App")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MixTitle', parent=styles['Heading2'], spaceAfter=12))
    styles.add(ParagraphStyle(name='TrackItem', parent=styles['Normal'], leftIndent=20, spaceAfter=3))
    content = []
    title = Paragraph(f"Tracklists for {artist_name}", styles['Title'])
    content.append(title)
    content.append(Spacer(1, 0.25 * inch))
    mixes_with_tracklists = sum(1 for mix in mixes if mix.get("has_tracklist", False))
    total_tracks = sum(len(mix.get("tracks", [])) for mix in mixes)
    summary = Paragraph(f"Found {total_tracks} tracks across {mixes_with_tracklists} mixes with tracklists (total of {len(mixes)} mixes)", styles['Normal'])
    content.append(summary)
    content.append(Spacer(1, 0.25 * inch))
    generated = Paragraph(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}", styles['Italic'])
    content.append(generated)
    content.append(Spacer(1, 0.5 * inch))
    for mix in mixes:
        title_text = mix.get("title", "Untitled Mix")
        if mix.get("date"):
            title_text = f"{mix.get('date')} - {title_text}"
        content.append(Paragraph(title_text, styles['MixTitle']))
        tracks = mix.get("tracks", [])
        if tracks:
            for i, track in enumerate(tracks):
                track_text = f"{i + 1}. {track}"
                content.append(Paragraph(track_text, styles['TrackItem']))
        else:
            content.append(Paragraph("No tracklist available", styles['TrackItem']))
        content.append(Spacer(1, 0.1 * inch))
    try:
        doc.build(content)
    except Exception as build_error:
        logger.error(f"Error building PDF content: {build_error}")
        raise # Re-raise the error after logging
        
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

# Main entry point for development server (not used by Gunicorn)
# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 8080))
#     debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
#     host = os.environ.get("FLASK_HOST", "127.0.0.1")
#     logger.info(f"Starting Flask server on {host}:{port} (Debug: {debug_mode})")
#     app.run(host=host, port=port, debug=debug_mode)

# Note: The if __name__ == "__main__" block is commented out 
# as Gunicorn is used for production (specified in Procfile).
