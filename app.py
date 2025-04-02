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
from reportlab.pdfgen import canvas
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
        "meta": job.meta # Include all metadata
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

# --- PDF Generation Background Job Routes ---
@app.route("/start_pdf_job", methods=['POST'])
def start_pdf_job():
    """Enqueue a PDF generation job and return the job ID."""
    artist_name = request.form.get("artist_name", "")
    
    if not artist_name:
        return jsonify({"error": "Artist name is required"}), 400
    
    if q is None:
        logger.error("Cannot enqueue PDF job: RQ Queue not available")
        return jsonify({"error": "Background task queue is not available"}), 503

    try:
        logger.info(f"Enqueuing PDF generation job for artist: {artist_name}")
        
        # Enqueue PDF generation as a background job
        # First, fetch the data, then generate the PDF
        job = q.enqueue('app.generate_pdf_background', artist_name, job_timeout=3600)  # 60 minutes timeout
        
        logger.info(f"PDF job enqueued with ID: {job.id}")
        return jsonify({"job_id": job.id})
    
    except Exception as e:
        logger.error(f"Error enqueuing PDF job for {artist_name}: {str(e)}")
        return jsonify({"error": f"An error occurred while starting PDF generation: {str(e)}"}), 500

@app.route("/get_pdf/<job_id>")
def get_pdf(job_id):
    """Retrieve a generated PDF from a completed job."""
    if q is None:
        return jsonify({"error": "Background task queue is not available"}), 503
    
    try:
        job = q.fetch_job(job_id)
    except Exception as e:
        logger.error(f"Error fetching PDF job {job_id}: {e}")
        return jsonify({"error": "Failed to fetch PDF job"}), 500

    if job is None:
        return jsonify({"error": "PDF job not found"}), 404

    if not job.is_finished:
        return jsonify({"error": "PDF generation not yet complete", "status": job.get_status()}), 202

    if job.is_failed:
        error_message = job.exc_info.strip().split('\n')[-1] if job.exc_info else "Unknown error"
        return jsonify({"error": f"PDF generation failed: {error_message}"}), 500

    if not job.result:
        return jsonify({"error": "PDF generation completed but no result was returned"}), 500

    # Extract data from job result
    pdf_data = job.result.get("pdf_data")
    artist_name = job.result.get("artist_name")
    
    if not pdf_data:
        return jsonify({"error": "PDF generation result is missing data"}), 500

    # Prepare response with PDF file
    filename = f"tracklists_{artist_name.replace(' ', '_')}.pdf"
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/background_pdf")
def background_pdf():
    """Show loading page for background PDF generation."""
    artist_name = request.args.get("artist_name", "")
    if not artist_name:
        return render_template('index.html', error="Please enter an artist name", year=datetime.datetime.now().year)
    
    try:
        return render_template('background_pdf.html', artist_name=artist_name, year=datetime.datetime.now().year)
    except Exception as e:
        logger.error(f"Error showing background PDF page for {artist_name}: {str(e)}")
        return render_template('index.html', artist_name=artist_name, error=f"An error occurred: {str(e)}", year=datetime.datetime.now().year)

# --- PDF Generation Functions ---
def generate_pdf_background(artist_name):
    """Background job function for PDF generation.
    This runs in the worker process, not the web process."""
    try:
        logger.info(f"Background job: Generating PDF for artist: {artist_name}")
        
        # Access the current job to update progress
        from rq.job import get_current_job
        job = get_current_job()
        
        # Set initial progress
        if job:
            job.meta['progress'] = 5
            job.meta['status'] = 'Fetching artist data...'
            job.save_meta()
        
        # Fetch the data
        mixes = scraper.main(artist_name)
        
        if not mixes:
            return {"error": f"No tracklists found for '{artist_name}'"}
        
        # Log the total number of mixes found - using all mixes without limitation
        logger.info(f"Found {len(mixes)} total mixes for {artist_name}. Generating complete PDF with all mixes.")
        
        # Update progress after fetching data
        if job:
            job.meta['progress'] = 30
            job.meta['status'] = f'Found {len(mixes)} mixes. Starting PDF generation...'
            job.meta['total_mixes'] = len(mixes)
            job.meta['current_mix'] = 0
            job.save_meta()
        
        # Generate the PDF with all mixes (removed the mix limitation)
        pdf_data = generate_pdf(artist_name, mixes, job)
        
        # Final progress update
        if job:
            job.meta['progress'] = 100
            job.meta['status'] = 'PDF generation complete!'
            job.save_meta()
        
        # Return both the PDF data and the artist name
        return {
            "artist_name": artist_name,
            "pdf_data": pdf_data,
            "tracks_count": sum(len(mix.get("tracks", [])) for mix in mixes),
            "mixes_count": len(mixes)
        }
        
    except Exception as e:
        # Update progress on error
        if 'job' in locals() and job:
            job.meta['error'] = str(e)
            job.save_meta()
        logger.error(f"Error in background PDF generation for {artist_name}: {str(e)}")
        raise

# --- Keep existing PDF generation function ---
def generate_pdf(artist_name, mixes, job=None):
    """Generate a PDF document with all tracklists for an artist."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"Tracklists for {artist_name}", author="The Digger App")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MixTitle', parent=styles['Heading2'], spaceAfter=12))
    styles.add(ParagraphStyle(name='TrackItem', parent=styles['Normal'], leftIndent=20, spaceAfter=3))
    content = []
    
    # Create PDF content in batches to improve performance
    title = Paragraph(f"Tracklists for {artist_name}", styles['Title'])
    content.append(title)
    content.append(Spacer(1, 0.25 * inch))
    
    # Calculate stats once to avoid repeated calculations
    mixes_with_tracklists = sum(1 for mix in mixes if mix.get("has_tracklist", False))
    total_tracks = sum(len(mix.get("tracks", [])) for mix in mixes)
    
    summary = Paragraph(f"Found {total_tracks} tracks across {mixes_with_tracklists} mixes with tracklists (total of {len(mixes)} mixes)", styles['Normal'])
    content.append(summary)
    content.append(Spacer(1, 0.25 * inch))
    generated = Paragraph(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}", styles['Italic'])
    content.append(generated)
    content.append(Spacer(1, 0.5 * inch))
    
    # Update progress at the start of PDF generation
    if job:
        job.meta['progress'] = 35
        job.meta['status'] = 'Creating PDF document structure...'
        job.save_meta()
    
    # Calculate progress increment per mix
    progress_increment = 60 / max(len(mixes), 1)  # 35% to 95%
    current_progress = 35
    
    # Process each mix
    for i, mix in enumerate(mixes):
        title_text = mix.get("title", "Untitled Mix")
        if mix.get("date"):
            title_text = f"{mix.get('date')} - {title_text}"
        content.append(Paragraph(title_text, styles['MixTitle']))
        
        # Update progress and status periodically
        if job and i % max(1, len(mixes) // 10) == 0:  # Update every ~10% of mixes
            current_progress = min(35 + progress_increment * i, 95)
            job.meta['progress'] = round(current_progress)
            job.meta['status'] = f'Processing mix {i+1} of {len(mixes)}: {title_text}'
            job.meta['current_mix'] = i + 1
            job.save_meta()
        
        tracks = mix.get("tracks", [])
        if tracks:
            # Process tracks in chunks for better memory handling
            for i, track in enumerate(tracks):
                track_text = f"{i + 1}. {track}"
                content.append(Paragraph(track_text, styles['TrackItem']))
                
                # Build the document in chunks if it gets very large
                # Reduced chunk size for very large catalogs
                chunk_threshold = 300 if len(mixes) > 200 else 500
                if len(content) > chunk_threshold:
                    logger.info(f"Building PDF document chunk with {len(content)} elements")
                    doc.build(content, canvasmaker=NumberedCanvas)
                    content = []  # Reset content for next chunk
        else:
            content.append(Paragraph("No tracklist available", styles['TrackItem']))
        
        content.append(Spacer(1, 0.1 * inch))
        
        # Generate PDF in chunks after each mix for very large catalogs
        if len(mixes) > 300 and len(content) > 100:
            logger.info(f"Building PDF document chunk after mix with {len(content)} elements")
            doc.build(content, canvasmaker=NumberedCanvas)
            content = []  # Reset content for next chunk
    
    # Final progress update before building the document
    if job:
        job.meta['progress'] = 95
        job.meta['status'] = 'Finalizing PDF document...'
        job.save_meta()
    
    try:
        # Build final document with any remaining content
        if content:
            doc.build(content)
    except Exception as build_error:
        logger.error(f"Error building PDF content: {build_error}")
        raise # Re-raise the error after logging
        
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

# Custom canvas for PDF generation with page numbers
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page numbers to each page"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        # Add page numbers at the bottom of each page
        self.setFont("Helvetica", 8)
        self.drawRightString(
            letter[0] - 24, 24, f"Page {self._pageNumber} of {page_count}"
        )

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
    """Redirect to background PDF generation for better reliability."""
    artist_name = request.args.get("artist_name", "")
    if not artist_name:
        return make_response(jsonify({"error": "Artist name is required"}), 400)
    
    # Redirect to the background PDF page instead
    logger.info(f"Redirecting direct PDF request for {artist_name} to background processing")
    return redirect(url_for('background_pdf', artist_name=artist_name))

@app.route("/direct_pdf_download") # This also remains synchronous
def direct_pdf_download():
    """Redirect to background PDF generation for better reliability."""
    artist_name = request.args.get("artist_name", "")
    if not artist_name:
        return render_template('index.html', error="Please enter an artist name", year=datetime.datetime.now().year)
    
    # Redirect to the background PDF page instead
    logger.info(f"Redirecting direct PDF download for {artist_name} to background processing")
    return redirect(url_for('background_pdf', artist_name=artist_name))

# Main entry point for development server (not used by Gunicorn)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    logger.info(f"Starting Flask server on {host}:{port} (Debug: {debug_mode})")
    app.run(host=host, port=port, debug=debug_mode)

# Note: The if __name__ == "__main__" block is commented out 
# as Gunicorn is used for production (specified in Procfile).
