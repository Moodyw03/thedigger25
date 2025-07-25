from flask import Flask, jsonify, request, make_response, render_template, redirect, url_for
from flask_cors import CORS
import datetime
import logging
import os
import time
import requests
import urllib.parse
import re
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
from track_formatter import format_track_for_pdf
import json
import redis # Add redis import for caching checks
# Import the Discogs API client
import discogs

# RQ imports
from redis import from_url as redis_from_url
from rq import Queue

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple in-memory cache for YouTube video searches
video_id_cache = {}
# Set a cache expiry time (24 hours in seconds)
CACHE_EXPIRY = int(os.environ.get('CACHE_EXPIRY', 86400))

app = Flask(__name__)
CORS(app)

# --- Redis & RQ Setup ---
# Connect to Redis using the URL provided by Railway (or default)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_TTL = int(os.getenv("CACHE_TTL", 86400)) # Cache TTL in seconds (default: 24 hours)

# +++ Added logging for the REDIS_URL +++
logger.info(f"Read REDIS_URL from environment: '{REDIS_URL}'")
# +++ End logging add +++

redis_conn = None
q = None

try:
    # Establish Redis connection for RQ
    # +++ Added logging +++
    logger.info(f"Attempting RQ Redis connection using URL: '{REDIS_URL}'")
    # +++ Added validation block +++
    if not REDIS_URL or not (REDIS_URL.startswith('redis://') or REDIS_URL.startswith('rediss://')):
         logger.error(f"Invalid Redis URL scheme or URL is empty: '{REDIS_URL}'")
         raise ValueError("Redis URL is missing or does not start with redis:// or rediss://")
    # +++ End validation block +++
    redis_conn = redis.from_url(REDIS_URL)
    redis_conn.ping() # Check connection
    logger.info(f"Successfully connected to Redis for RQ at {REDIS_URL.split('@')[-1]}") # Avoid logging password
    
    # Create the RQ queue
    q = Queue(connection=redis_conn)
    logger.info("RQ Queue initialized successfully.")
    
except redis.exceptions.ConnectionError as e:
    # +++ Updated logging +++
    logger.error(f"Failed to connect to Redis for RQ with URL '{REDIS_URL}': {e}. Background tasks will not be available.")
    q = None
# +++ Added specific ValueError catch +++
except ValueError as e: # Catch the explicit validation error
    logger.error(f"Failed due to invalid Redis URL '{REDIS_URL}' for RQ: {e}. Background tasks will not be available.")
    q = None
# +++ Added generic Exception catch +++
except Exception as e: # Generic catch-all
    logger.error(f"An unexpected error occurred during RQ Redis setup with URL '{REDIS_URL}': {e}", exc_info=True)
    q = None

# Also establish a separate connection for general caching (optional but good practice)
# This uses the same REDIS_URL but avoids potential conflicts if RQ uses specific DB numbers
redis_cache_client = None
try:
    # Use decode_responses=False to store raw bytes/strings for flexibility
    # +++ Added logging +++
    logger.info(f"Attempting Cache Redis connection using URL: '{REDIS_URL}'")
    # +++ Added validation block +++
    if not REDIS_URL or not (REDIS_URL.startswith('redis://') or REDIS_URL.startswith('rediss://')):
         logger.error(f"Invalid Redis URL scheme or URL is empty: '{REDIS_URL}'")
         raise ValueError("Redis URL is missing or does not start with redis:// or rediss://")
    # +++ End validation block +++
    redis_cache_client = redis.from_url(REDIS_URL, decode_responses=False)
    redis_cache_client.ping()
    logger.info(f"Successfully connected to Redis for general caching at {REDIS_URL.split('@')[-1]}")
except redis.exceptions.ConnectionError as e:
    # +++ Updated logging +++
    logger.error(f"Failed to connect to Redis for caching with URL '{REDIS_URL}': {e}. Caching features will be disabled.")
    redis_cache_client = None
# +++ Added specific ValueError catch +++
except ValueError as e: # Catch the explicit validation error
    logger.error(f"Failed due to invalid Redis URL '{REDIS_URL}' for caching: {e}. Caching features will be disabled.")
    redis_cache_client = None
# +++ Added generic Exception catch +++
except Exception as e: # Generic catch-all
    logger.error(f"An unexpected error occurred during Cache Redis setup with URL '{REDIS_URL}': {e}", exc_info=True)
    redis_cache_client = None

@app.route("/")
def index():
    """Render the home page with search form."""
    return render_template('index.html', year=datetime.datetime.now().year)

@app.route("/search", methods=['POST']) # Changed to POST for clarity
def start_search_job():
    """Enqueue a search job, checking cache first, and return the job ID or cached data."""
    artist_name = request.form.get("artist_name", "")
    
    if not artist_name:
        return jsonify({"error": "Artist name is required"}), 400
    
    # --- Check Cache Before Queuing ---
    cache_key = f"artist_cache:{artist_name.lower().replace(' ', '_')}" # Consistent key
    if redis_cache_client:
        try:
            cached_data = redis_cache_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit in /search for artist: {artist_name}. Returning cached data.")
                try:
                    # Decode bytes then parse JSON
                    artist_data = json.loads(cached_data.decode('utf-8'))
                    return jsonify({ "status": "cached", "data": artist_data })
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding cached JSON for {artist_name} in /search: {e}. Cache entry corrupted? Proceeding to queue job.")
                    # Optionally, delete the corrupted key
                    try:
                        redis_cache_client.delete(cache_key)
                        logger.info(f"Deleted corrupted cache entry for {artist_name}")
                    except:
                        pass
            else:
                logger.info(f"Cache miss in /search for artist: {artist_name}. Proceeding to queue job.")
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error checking cache in /search for {artist_name}: {e}. Proceeding to queue job.")

    # --- Queue Job if Cache Miss or Redis Error ---
    if q is None:
        logger.error("Cannot enqueue job: RQ Queue not available (Redis connection failed).")
        return jsonify({"error": "Background task queue is not available"}), 503 # Service Unavailable

    try:
        logger.info(f"Enqueuing search job for artist: {artist_name}")
        
        # INCREASED TIMEOUT: 1 hour (3600 seconds) instead of 30 minutes (1800 seconds)
        # for better handling of large artist catalogs
        job = q.enqueue(
            'main.main', 
            artist_name, 
            job_timeout=3600,     # 60 minutes timeout for large catalogs (increased from 30 minutes)
            result_ttl=86400,     # Keep results for 24 hours
            description=f"Artist search: {artist_name}",  # Better job description for monitoring
            meta={
                'artist_name': artist_name,
                'enqueued_at': time.time(),
                'status': 'Queued',
                'progress': 0
            }
        )
        
        logger.info(f"Job enqueued with ID: {job.id}")
        # Return the job ID to the client
        return jsonify({
            "job_id": job.id, 
            "status": "queued",
            "artist_name": artist_name,
            "message": "Your search has been queued. Results will be ready soon."
        })
    
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
    # For PDF jobs, exclude binary data from JSON response
    if isinstance(job.result, dict) and "pdf_data" in job.result:
        # Create a copy without the binary data
        result_data = {k: v for k, v in job.result.items() if k != "pdf_data"}
        return jsonify({
            "status": "finished", 
            "data": result_data,
            "has_pdf": True,
            "pdf_url": f"/get_pdf/{job_id}"
        })
    else:
        # For non-PDF jobs, return the full result
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
        
        # Enqueue PDF generation as a background job with longer timeout
        job = q.enqueue(
            'app.generate_pdf_background', 
            artist_name, 
            job_timeout=3600,     # 60 minutes timeout
            result_ttl=86400      # Keep results for 24 hours
        )
        
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
    
    # Use a different approach to handle large documents without losing content
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import letter
    
    # Create a BaseDocTemplate instead of SimpleDocTemplate
    doc = BaseDocTemplate(
        buffer, 
        pagesize=letter,
        title=f"Tracklists for {artist_name}",
        author="The Digger App"
    )
    
    # Create a frame for the content and add it to a page template
    frame = Frame(
        doc.leftMargin, 
        doc.bottomMargin, 
        doc.width, 
        doc.height,
        id='normal'
    )
    template = PageTemplate(id='all_frames', frames=frame, onPage=add_page_number)
    doc.addPageTemplates([template])
    
    # Add styles for PDF content
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MixTitle', parent=styles['Heading2'], spaceAfter=12))
    styles.add(ParagraphStyle(name='TrackItem', parent=styles['Normal'], leftIndent=20, spaceAfter=3))
    
    # Store all content in a single list that will be built once at the end
    all_content = []
    
    # Create PDF title and header information
    title = Paragraph(f"Tracklists for {artist_name}", styles['Title'])
    all_content.append(title)
    all_content.append(Spacer(1, 0.25 * inch))
    
    # Calculate stats once to avoid repeated calculations
    mixes_with_tracklists = sum(1 for mix in mixes if mix.get("has_tracklist", False))
    total_tracks = sum(len(mix.get("tracks", [])) for mix in mixes)
    
    summary = Paragraph(f"Found {total_tracks} tracks across {mixes_with_tracklists} mixes with tracklists (total of {len(mixes)} mixes)", styles['Normal'])
    all_content.append(summary)
    all_content.append(Spacer(1, 0.25 * inch))
    generated = Paragraph(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}", styles['Italic'])
    all_content.append(generated)
    all_content.append(Spacer(1, 0.5 * inch))
    
    # Update progress at the start of PDF generation
    if job:
        job.meta['progress'] = 35
        job.meta['status'] = 'Creating PDF document structure...'
        job.save_meta()
    
    # Calculate progress increment per mix
    progress_increment = 60 / max(len(mixes), 1)  # 35% to 95%
    current_progress = 35
    
    # Process each mix and add to all_content
    for i, mix in enumerate(mixes):
        title_text = mix.get("title", "Untitled Mix")
        if mix.get("date"):
            title_text = f"{mix.get('date')} - {title_text}"
        all_content.append(Paragraph(title_text, styles['MixTitle']))
        
        # Update progress and status periodically
        if job and i % max(1, len(mixes) // 10) == 0:  # Update every ~10% of mixes
            current_progress = min(35 + progress_increment * i, 95)
            job.meta['progress'] = round(current_progress)
            job.meta['status'] = f'Processing mix {i+1} of {len(mixes)}: {title_text}'
            job.meta['current_mix'] = i + 1
            job.save_meta()
        
        tracks = mix.get("tracks", [])
        if tracks:
            # Process all tracks for this mix
            for j, track in enumerate(tracks):
                track_text = f"{j + 1}. {format_track_for_pdf(track)}"
                all_content.append(Paragraph(track_text, styles['TrackItem']))
        else:
            all_content.append(Paragraph("No tracklist available", styles['TrackItem']))
        
        all_content.append(Spacer(1, 0.2 * inch))
    
    # Final progress update before building the document
    if job:
        job.meta['progress'] = 95
        job.meta['status'] = 'Finalizing PDF document...'
        job.save_meta()
    
    try:
        # Build the document once with all content
        doc.build(all_content)
        
        logger.info(f"Successfully built PDF with {total_tracks} tracks across {len(mixes)} mixes")
    except Exception as build_error:
        logger.error(f"Error building PDF content: {build_error}")
        raise # Re-raise the error after logging
        
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

# Function to add page numbers to PDF pages
def add_page_number(canvas, doc):
    """Add page number to each page of the PDF"""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    page_num = canvas.getPageNumber()
    canvas.drawRightString(
        letter[0] - 24, 
        24, 
        f"Page {page_num} of {doc.page}"
    )
    canvas.restoreState()

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

@app.route("/search_video")
def search_video():
    """Search for a YouTube video and return the video ID."""
    query = request.args.get("query", "")
    source = request.args.get("source", "djset")  # djset or discogs - helps customize search
    
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    # Check cache first
    cache_key = query.lower() + ":" + source
    current_time = time.time()
    
    if cache_key in video_id_cache:
        cached_item = video_id_cache[cache_key]
        # If the cache hasn't expired
        if current_time - cached_item["timestamp"] < CACHE_EXPIRY:
            logger.info(f"Cache hit for query: {query} (source: {source})")
            return jsonify({"videoId": cached_item["video_id"]})
    
    try:
        logger.info(f"Searching YouTube for: {query} (source: {source})")
        
        # Format query for YouTube search - ENHANCED ALGORITHM FOR EXACT MATCHING
        enhanced_query = query
        
        # Parse artist and title if this is in the format "Artist - Title"
        artist = None
        title = None
        label_info = None
        catalog_num = None
        release_year = None
        
        # Extract additional context from query if available
        if " - " in query:
            # First clean up any bracketed track numbers at the beginning
            cleaned_query = re.sub(r'^\s*\[\d+\]\s*', '', query)
            
            # Then try to split on artist-title separator
            parts = cleaned_query.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
            
            # Check if title has a label in square brackets at the end
            label_in_title = re.search(r'\[([^\]]+)\]$', title)
            if label_in_title:
                label_info = label_in_title.group(1).strip()
                # Remove the label part from the title
                title = re.sub(r'\s*\[[^\]]+\]$', '', title).strip()
                
                # Check if label_info contains a label and catalog number separated by dash
                if " - " in label_info:
                    label_parts = label_info.split(" - ", 1)
                    # If the second part looks like a catalog number (contains digits)
                    if re.search(r'\d', label_parts[1]):
                        label_info = label_parts[0].strip()
                        catalog_num = label_parts[1].strip()
                    else:
                        # Otherwise assume first part might be catalog
                        if re.search(r'\d', label_parts[0]):
                            catalog_num = label_parts[0].strip()
                            label_info = label_parts[1].strip()
            
            # If no catalog number found yet, try additional patterns
            if not catalog_num:
                # Extract catalog number if present (common formats: ABC-123, CATALOGUE123, etc.)
                catalog_patterns = [
                    r'\b([A-Z0-9]+-?[A-Z0-9]+)\b',  # Standard format
                    r'\b([A-Z]{2,}[\s\-]?\d+[A-Z]?)\b',  # Extended format
                    r'([A-Z]+\d+[A-Z]*)',  # Compact format
                    r'(\d+[A-Z]+\d*)'  # Numeric prefix format
                ]
                
                for pattern in catalog_patterns:
                    catalog_match = re.search(pattern, query)
                    if catalog_match:
                        potential_catno = catalog_match.group(1)
                        # Verify it's not just a common word
                        if (len(potential_catno) >= 4 and 
                            not potential_catno.lower() in ['remix', 'track', 'edit', 'version']):
                            catalog_num = potential_catno
                            break
                        
            # Extract year info if present (4 digits usually representing a year)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                release_year = year_match.group(1)
            
            # Remove quotes if they exist
            if artist.startswith('"') and artist.endswith('"'):
                artist = artist[1:-1]
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
                
            # Clean up artist and title 
            clean_title = re.sub(r'\s*\([^)]*\)\s*|\s*\[[^\]]*\]\s*', ' ', title).strip()
            clean_artist = re.sub(r'\s*\([^)]*\)\s*|\s*\[[^\]]*\]\s*', ' ', artist).strip()
            
            # Create more targeted search queries
            if "remix" in title.lower() or "mix" in title.lower():
                # For remix tracks, include the remix info in the search
                enhanced_query = f"{clean_artist} {title}"
            else:
                # For original tracks, use the cleaned title and artist
                enhanced_query = f"{clean_artist} {clean_title}"
        
        # Determine music genre to optimize search
        electronic_keywords = ["techno", "house", "trance", "dnb", "drum and bass", "dubstep", "ambient", 
                              "electronica", "electronic", "edm", "dj", "remix", "club", "minimal",
                              "deep", "experimental", "idm", "industrial"]
                              
        underground_labels = ["hessle audio", "hyperdub", "warp", "ostgut ton", "berghain", "perlon", 
                            "planet mu", "r&s", "l.i.e.s", "pcp", "houndstooth", "bpitch", "tresor",
                            "dekmantel", "hotflush", "clone", "stroboscopic", "livity sound", 
                            "whities", "church", "ninja tune", "warp", "innervisions", "diynamic",
                            "running back", "kompakt", "aniara"]
                            
        is_electronic = (any(keyword in query.lower() for keyword in electronic_keywords) or 
                        (label_info and any(label.lower() in label_info.lower() for label in underground_labels)))
        is_underground = (label_info and any(label.lower() in label_info.lower() for label in underground_labels))
        
        # Add specific genre tags to improve search relevance
        if is_electronic:
            # For underground electronic music, don't add "official" as many tracks don't have official videos
            if "techno" in query.lower():
                enhanced_query = f"{enhanced_query} techno"
            elif "house" in query.lower():
                enhanced_query = f"{enhanced_query} house"
            elif "ambient" in query.lower():
                enhanced_query = f"{enhanced_query} ambient"
            elif "drum and bass" in query.lower() or "dnb" in query.lower():
                enhanced_query = f"{enhanced_query} drum and bass"
            else:
                # Generic electronic music
                enhanced_query = f"{enhanced_query} electronic"
            
            # Add "track" for electronic music to avoid mixes and playlists
            if "track" not in enhanced_query.lower():
                enhanced_query = f"{enhanced_query} track"
        else:
            # Add "music" for non-electronic music if not already present
            if "music" not in enhanced_query.lower():
                enhanced_query = f"{enhanced_query} music"
            
            # Only add "official" if it's likely to be a mainstream track
            mainstream_keywords = ["pop", "rock", "official", "records", "vevo", "sony", "warner", "universal"]
            is_mainstream = any(keyword in query.lower() for keyword in mainstream_keywords)
            
            if is_mainstream and "official" not in enhanced_query.lower():
                enhanced_query = f"{enhanced_query} official"
        
        # Create multiple search queries to try in order of specificity
        search_queries = []
        
        # Special handling for Discogs searches
        if source == "discogs" and artist and title:
            # Discogs searches should emphasize exact matching with catalog numbers
            if catalog_num:
                # 1. Most precise search includes catalog number which is highly specific
                search_queries.append(f'"{artist}" "{title}" {catalog_num}')
                # 1a. Add variant with label to further improve specificity
                if label_info:
                    search_queries.append(f'"{artist}" "{title}" {catalog_num} {label_info}')
                # 1b. Add variant with explicit music context for catalog searches
                search_queries.append(f'"{artist}" "{title}" {catalog_num} music')
            
            # 2. Add quoted artist and title for exact match
            search_queries.append(f'"{artist}" "{title}"')
            
            # 3. Add label info for context with different priority levels
            if label_info:
                search_queries.append(f'"{artist}" "{title}" {label_info}')
                # 3a. Add label with explicit music context
                search_queries.append(f'"{artist}" "{title}" {label_info} music')
                
            # 4. Add year for temporal context
            if release_year:
                search_queries.append(f'"{artist}" "{title}" {release_year}')
                # 4a. Combine year with label for stronger context
                if label_info:
                    search_queries.append(f'"{artist}" "{title}" {label_info} {release_year}')
                
            # 5. Add title with music/track keyword to improve relevance
            search_queries.append(f'"{artist}" "{title}" music track')
                
            # 6. Full context search
            full_context = f'{artist} {title}'
            if catalog_num:
                full_context += f' {catalog_num}'
            if label_info:
                full_context += f' {label_info}'
            if release_year:
                full_context += f' {release_year}'
            search_queries.append(full_context)
            
            # 7. For electronic music specifically
            if is_electronic:
                # Add electronic music specific context
                search_queries.append(f'"{artist}" "{title}" electronic vinyl')
                if label_info:
                    search_queries.append(f'"{artist}" "{title}" {label_info} electronic')
                # Add specific format context for electronic music
                search_queries.append(f'"{artist}" "{title}" 12 inch')
                search_queries.append(f'"{artist}" "{title}" EP')
                
            # 8. Add individual term searches for better matching
            title_only_query = f'"{title}"'
            if title_only_query not in search_queries and len(title) > 3:
                search_queries.append(title_only_query + f' by "{artist}"')
                
            # 9. For remixes, add special handling
            if 'remix' in title.lower():
                remix_parts = re.match(r'(.+?)(?:\s*\(([^)]+)\s*remix\))', title, re.IGNORECASE)
                if remix_parts:
                    base_track = remix_parts.group(1).strip()
                    remixer = remix_parts.group(2).strip()
                    # Try searching with the remix info in different formats
                    search_queries.append(f'"{base_track}" "{remixer}" remix')
                    search_queries.append(f'"{artist}" "{base_track}" {remixer} remix')
                    
            # 10. Add format-specific searches for better matching
            format_keywords = ['vinyl', 'digital', '12"', 'EP', 'single', 'release']
            for format_keyword in format_keywords:
                if format_keyword.lower() in query.lower():
                    search_queries.append(f'"{artist}" "{title}" {format_keyword}')
                    break
                    
            # 11. Add label-specific searches without quotes for broader matching
            if label_info and len(label_info) > 3:
                search_queries.append(f'{artist} {title} {label_info} records')
                search_queries.append(f'{artist} {title} {label_info} music')
                
            # 12. Add searches optimized for underground electronic music
            if is_underground and label_info:
                underground_keywords = ['techno', 'house', 'minimal', 'electronic', 'underground']
                for keyword in underground_keywords:
                    if keyword in query.lower() or keyword in label_info.lower():
                        search_queries.append(f'"{artist}" "{title}" {keyword}')
                        search_queries.append(f'"{artist}" "{title}" {label_info} {keyword}')
                        break
        else:
            # Regular DJ set searches
            # 1. Most specific search with artist, title and extra context
            if artist and title:
                search_queries.append(enhanced_query)
                
                # 2. Add more specific query with quotes for exact match
                exact_query = f'"{artist}" "{title}"'
                if exact_query != enhanced_query:
                    search_queries.append(exact_query)
                
                # 3. Add catalog number for better matching of specific releases
                if catalog_num and catalog_num not in enhanced_query:
                    search_queries.append(f"{artist} {title} {catalog_num}")
                    
                # 4. Add very specific underground electronic query with label
                if is_underground and label_info:
                    search_queries.append(f"{artist} {title} {label_info}")
        
        # Fallback: original query
        if enhanced_query not in search_queries:
            search_queries.append(enhanced_query)
        
        logger.info(f"Search queries to try: {search_queries}")
        
        # Try each search query in order until we get good results
        video_ids = []
        used_query = None
        search_url = None
        
        for search_query in search_queries:
            encoded_query = urllib.parse.quote(search_query)
            
            # Make request to YouTube search
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(
                f"https://www.youtube.com/results?search_query={encoded_query}",
                headers=headers
            )
            
            if response.status_code == 200:
                # Extract video IDs using multiple pattern matching approaches
                video_ids = []
                patterns = [
                    '"videoId":"', 
                    'watch?v=',
                    '/embed/',
                    '/v/'
                ]
                
                for pattern in patterns:
                    start_idx = response.text.find(pattern)
                    if start_idx != -1:
                        start_idx += len(pattern)
                        
                        # Determine end of video ID based on which pattern was found
                        if pattern == '"videoId":"':
                            end_idx = response.text.find('"', start_idx)
                        else:
                            # For URL patterns, look for ending delimiters
                            end_idx = next((response.text.find(c, start_idx) for c in ['"', '&', '#', '?', ' '] 
                                          if response.text.find(c, start_idx) != -1), len(response.text))
                        
                        if end_idx != -1:
                            found_id = response.text[start_idx:end_idx]
                            # Basic validation - YouTube IDs are usually 11 characters
                            if len(found_id) == 11:
                                video_ids.append(found_id)
                                logger.info(f"Found video ID using pattern '{pattern}': {found_id}")
                
                # If no IDs found with patterns, try regex as a fallback
                if not video_ids:
                    regex_matches = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', response.text)
                    if regex_matches:
                        video_ids = regex_matches
                        logger.info(f"Found {len(video_ids)} video IDs using regex fallback")
                
                # If we found any video IDs with our robust extraction
                if video_ids:
                    used_query = search_query
                    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
                    break
        
        # If no results found with any query, return an error
        if not video_ids:
            return jsonify({"error": "No videos found for any search query"}), 404
        
        # Get unique video IDs - remove duplicates
        unique_video_ids = list(dict.fromkeys(video_ids))
        
        # Filter out YouTube Mix/Playlist results to avoid long DJ mixes
        filtered_ids = [vid for vid in unique_video_ids if "list=" not in response.text.split(vid)[1].split("<")[0]]
        
        # If no filtered IDs, use the unique IDs
        if not filtered_ids:
            filtered_ids = unique_video_ids
        
        # Look for exact matches in surrounding text with much larger context window
        best_match_id = None
        match_score = 0
        
        # Only perform advanced matching if we have both artist and title
        if artist and title and len(filtered_ids) > 1:
            # Check more results for precise matching
            for vid_index, vid in enumerate(filtered_ids[:15]):  # Check top 15 results for thoroughness
                # Find where this video ID appears in the response
                vid_pos = response.text.find(vid)
                if vid_pos > 0:
                    # Get a much larger chunk of text around the ID for better context matching
                    surrounding_text = response.text[max(0, vid_pos-400):min(len(response.text), vid_pos+400)].lower()
                    
                    # Calculate a match score for this result
                    score = 0
                    
                    # Check for exact artist match
                    if artist.lower() in surrounding_text:
                        score += 20
                        # Bonus for exact match with word boundaries
                        if re.search(r'\b' + re.escape(artist.lower()) + r'\b', surrounding_text):
                            score += 10
                    
                    # Check for exact title match
                    if title.lower() in surrounding_text:
                        score += 20
                        # Bonus for exact match with word boundaries
                        if re.search(r'\b' + re.escape(title.lower()) + r'\b', surrounding_text):
                            score += 10
                    
                    # Enhanced checks for electronic music and discogs releases
                    if catalog_num and catalog_num.lower() in surrounding_text:
                        score += 25  # Catalog numbers are highly specific identifiers
                    
                    # Check for label information
                    if label_info and label_info.lower() in surrounding_text:
                        score += 15
                    
                    # For Discogs sources, give more weight to catalog number and label matches
                    if source == "discogs":
                        if catalog_num and catalog_num.lower() in surrounding_text:
                            score += 15  # Extra boost for catalog match in discogs searches
                        
                        # Check for release year
                        if release_year and release_year in surrounding_text:
                            score += 10
                            
                        # Additional content indicators for Discogs searches
                        good_indicators = ['official', 'full track', 'release', 'records', 'vinyl', 'album', 'single', 'EP', '12 inch', 'original mix']
                        bad_indicators = ['mix compilation', 'megamix', 'mixtape', 'playlist', 'dj mix', 'full album', 'preview', 'live set', 'radio show']
                        
                        # Bonus for good indicators
                        for indicator in good_indicators:
                            if indicator in surrounding_text:
                                score += 5
                                
                        # Penalty for bad indicators
                        for indicator in bad_indicators:
                            if indicator in surrounding_text:
                                score -= 15
                                
                        # Special handling for electronic music labels and formats
                        electronic_indicators = ['techno', 'house', 'minimal', 'electronic', 'underground', 'vinyl', '12"']
                        for indicator in electronic_indicators:
                            if indicator in surrounding_text and (label_info and indicator in label_info.lower()):
                                score += 8  # Boost for matching electronic music context
                                
                        # Boost for exact catalog number patterns commonly used in electronic music
                        if catalog_num:
                            # Check for catalog patterns like "ABC001", "XYZ-123", etc.
                            catalog_pattern = re.compile(r'\b' + re.escape(catalog_num) + r'\b', re.IGNORECASE)
                            if catalog_pattern.search(surrounding_text):
                                score += 20  # Strong boost for exact catalog match
                                
                        # Check for track duration indicators (full tracks vs previews/clips)
                        duration_indicators = ['full track', 'complete', 'uncut', 'original length']
                        preview_indicators = ['preview', 'snippet', 'clip', '30 second', 'sample']
                        
                        for indicator in duration_indicators:
                            if indicator in surrounding_text:
                                score += 8
                                
                        for indicator in preview_indicators:
                            if indicator in surrounding_text:
                                score -= 12  # Penalize previews/clips
                                
                        # Boost for official channel uploads
                        official_channel_indicators = ['official', 'records', 'music', 'label']
                        for indicator in official_channel_indicators:
                            if indicator in surrounding_text:
                                score += 6
                    else:
                        # Regular DJ set logic (existing code)
                        # Check for release year
                        if release_year and release_year in surrounding_text:
                            score += 10
                            
                        # Additional content indicators for Discogs searches
                        good_indicators = ['official', 'full track', 'release', 'records', 'vinyl', 'album']
                        bad_indicators = ['mix compilation', 'megamix', 'mixtape', 'playlist', 'dj mix', 'full album', 'preview']
                        
                        # Bonus for good indicators
                        for indicator in good_indicators:
                            if indicator in surrounding_text:
                                score += 5
                                
                        # Penalty for bad indicators
                        for indicator in bad_indicators:
                            if indicator in surrounding_text:
                                score -= 15
                    
                    # Higher score for results that are closer to the top
                    score += max(0, 10 - vid_index)
                    
                    # Penalize videos with common issues
                    if "playlist" in surrounding_text or "mix compilation" in surrounding_text:
                        score -= 10
                    
                    # Update if this is the best match so far
                    if score > match_score:
                        match_score = score
                        best_match_id = vid
                        logger.info(f"Found better match: video ID {vid} with score {score}")
            
            # Only use the best match if it has a minimum score
            # For Discogs, require a higher score threshold since we need more precision
            min_score = 40 if source == "discogs" else 30
            
            if best_match_id and match_score >= min_score:
                video_id = best_match_id
                logger.info(f"Using best match: video ID {best_match_id} with score {match_score}")
            else:
                # Default to the first filtered ID
                video_id = filtered_ids[0]
                logger.info(f"No good exact match found, using first result: {video_id}")
        else:
            # For queries without artist/title separation, use the first result
            video_id = filtered_ids[0]
        
        # Save to cache
        video_id_cache[cache_key] = {
            "video_id": video_id,
            "timestamp": current_time
        }
        
        # Return the video ID and search URL
        return jsonify({
            "videoId": video_id,
            "query": used_query or enhanced_query,
            "searchUrl": search_url or f"https://www.youtube.com/results?search_query={urllib.parse.quote(enhanced_query)}"
        })
    
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return jsonify({"error": f"An error occurred while searching YouTube: {str(e)}"}), 500

# --- YouTube Audio Proxy Endpoint ---
@app.route("/audio_proxy")
def audio_proxy():
    """Proxies audio from YouTube videos that can't be embedded."""
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "Video ID is required"}), 400
    
    # Check cache first
    cache_key = f"audio_proxy_{video_id}"
    current_time = time.time()
    
    if cache_key in video_id_cache:
        cached_item = video_id_cache[cache_key]
        # If the cache hasn't expired
        if current_time - cached_item["timestamp"] < CACHE_EXPIRY:
            logger.info(f"Cache hit for audio proxy: {video_id}")
            return jsonify(cached_item["data"])
    
    try:
        # Use yt-dlp to extract YouTube video information
        import yt_dlp as youtube_dl
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            # Add additional options to improve extraction reliability
            'socket_timeout': 15,
            'retries': 3,
            'ignoreerrors': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            # Extract information without downloading
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            if not info:
                return jsonify({"error": "Could not extract video information"}), 404
            
            # Get the best audio format URL
            formats = info.get('formats', [])
            
            # First try to find audio-only formats (more efficient)
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            
            # Prepare response data
            result_data = {
                "success": True,
                "title": info.get('title', ''),
                "duration": info.get('duration', 0),
                "uploader": info.get('uploader', '')
            }
            
            if audio_formats:
                # Sort by quality (typically bitrate)
                audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                best_audio = audio_formats[0]
                audio_url = best_audio['url']
                
                # Add format info to response
                result_data.update({
                    "audio_url": audio_url,
                    "format": best_audio.get('format_note', 'unknown'),
                    "bitrate": best_audio.get('abr', 0)
                })
            else:
                # Fall back to any format with audio if no audio-only formats
                for format in formats:
                    if format.get('acodec') != 'none':
                        result_data.update({
                            "audio_url": format['url'],
                            "format": format.get('format_note', 'unknown'),
                            "is_video": True
                        })
                        break
                else:
                    return jsonify({"error": "No suitable audio format found"}), 404
            
            # Cache the result
            video_id_cache[cache_key] = {
                "data": result_data,
                "timestamp": current_time
            }
            
            return jsonify(result_data)
                
    except Exception as e:
        logger.error(f"Error proxying YouTube audio: {str(e)}")
        return jsonify({"error": f"Failed to extract audio: {str(e)}"}), 500

# --- Discogs API Routes ---
@app.route("/discogs/search_label")
def search_label():
    """Search for labels on Discogs"""
    label_name = request.args.get('label_name', '')
    page = request.args.get('page', 1, type=int)
    
    if not label_name:
        return jsonify({"error": "Label name is required"}), 400
    
    try:
        # Cache key for label search
        cache_key = f"discogs_label_search:{label_name.lower().replace(' ', '_')}:{page}"
        
        # Check cache first if Redis is available
        if redis_cache_client:
            try:
                cached_data = redis_cache_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for Discogs label search: {label_name}, page {page}")
                    return jsonify(json.loads(cached_data.decode('utf-8')))
            except Exception as e:
                logger.error(f"Redis error in label search: {str(e)}")
        
        # Cache miss or Redis not available, perform the search
        data = discogs.search_labels(label_name, page=page)
        
        # Cache the results if Redis is available
        if redis_cache_client:
            try:
                redis_cache_client.setex(
                    cache_key,
                    CACHE_TTL,
                    json.dumps(data).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Redis error caching label search: {str(e)}")
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in Discogs label search: {str(e)}")
        return jsonify({"error": f"Failed to search Discogs: {str(e)}"}), 500

@app.route("/discogs/label/<int:label_id>/releases")
def label_releases(label_id):
    """Get releases for a specific label from Discogs"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort = request.args.get('sort', 'year')
    sort_order = request.args.get('sort_order', 'desc')
    
    try:
        # Cache key for label releases
        cache_key = f"discogs_label_releases:{label_id}:{page}:{per_page}:{sort}:{sort_order}"
        
        # Check cache first if Redis is available
        if redis_cache_client:
            try:
                cached_data = redis_cache_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for Discogs label releases: {label_id}, page {page}")
                    return jsonify(json.loads(cached_data.decode('utf-8')))
            except Exception as e:
                logger.error(f"Redis error in label releases: {str(e)}")
        
        # Cache miss or Redis not available, fetch the releases
        data = discogs.get_label_releases(
            label_id, 
            page=page, 
            per_page=per_page,
            sort=sort,
            sort_order=sort_order
        )
        
        # Cache the results if Redis is available
        if redis_cache_client:
            try:
                redis_cache_client.setex(
                    cache_key,
                    CACHE_TTL,
                    json.dumps(data).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Redis error caching label releases: {str(e)}")
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in Discogs label releases: {str(e)}")
        return jsonify({"error": f"Failed to get Discogs releases: {str(e)}"}), 500

@app.route("/discogs/release/<int:release_id>")
def release_details(release_id):
    """Get detailed information about a specific release"""
    try:
        # Cache key for release details
        cache_key = f"discogs_release:{release_id}"
        
        # Check cache first if Redis is available
        if redis_cache_client:
            try:
                cached_data = redis_cache_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for Discogs release: {release_id}")
                    return jsonify(json.loads(cached_data.decode('utf-8')))
            except Exception as e:
                logger.error(f"Redis error in release details: {str(e)}")
        
        # Cache miss or Redis not available, fetch the release details
        data = discogs.get_release_details(release_id)
        
        # Cache the results if Redis is available
        if redis_cache_client:
            try:
                redis_cache_client.setex(
                    cache_key,
                    CACHE_TTL,
                    json.dumps(data).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Redis error caching release details: {str(e)}")
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in Discogs release details: {str(e)}")
        return jsonify({"error": f"Failed to get Discogs release: {str(e)}"}), 500

# Main entry point for development server (not used by Gunicorn)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    logger.info(f"Starting Flask server on {host}:{port} (Debug: {debug_mode})")
    app.run(host=host, port=port, debug=debug_mode)

# Note: The if __name__ == "__main__" block is commented out 
# as Gunicorn is used for production (specified in Procfile).
