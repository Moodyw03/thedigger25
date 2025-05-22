# The Digger

A tool for finding and listening to tracks played by your favorite DJs on MixesDB.

## Features

- Search for any DJ/artist on MixesDB
- View all tracks they've played in their sets
- Listen to tracks directly in the app (audio-only, starting at 2 minutes)
- Export tracklists as PDF for offline use
- Built-in YouTube search for finding exact tracks
- Minimal, clean interface with responsive design
- Fast caching system for improved performance
- Automatic rate limiting to prevent being blocked
- Background job processing for handling heavy operations

## 🔄 New Features and Improvements

### 🔉 YouTube Audio Proxy

The application now includes a YouTube audio proxy feature that allows playback of tracks that have embedding restrictions. When a track can't be embedded in the player, the app will automatically try to extract the audio directly.

### 📋 Combined Setup Process

The setup process has been simplified with a single script that works for both development and production environments:

```bash
# For development setup
./setup.sh

# For production setup
./setup.sh -p
```

### 🚀 Deployment Improvements

- Worker process now uses worker.py which is compatible with the Procfile
- Fixed cache management to improve performance with large track lists
- PDF generation has been improved to properly include all tracks

## Running the App

### Quick Start

1. Make sure you have Python 3.x installed
2. Clone this repository

```bash
git clone https://github.com/yourusername/the-digger.git
cd the-digger
```

3. Set up a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install dependencies

```bash
pip install -r requirements.txt
```

5. Start Redis (required for background job processing)
   Make sure Redis is installed and running locally on the default port (6379)
   or set the REDIS_URL environment variable to point to your Redis instance.

6. Run the application (choose one option)

#### Option A: Simple mode (all-in-one)

```bash
# Using the shell script (recommended for beginners)
./run-app.sh
```

#### Option B: Advanced mode (separate backend and worker)

For better performance and handling of long-running jobs, run the app using separate processes:

Terminal 1 - Start the Flask application:

```bash
./run-app.sh
```

Terminal 2 - Start the worker process:

```bash
python worker.py
```

With this setup, the Flask app handles web requests while the worker processes background jobs separately. This prevents long-running operations from blocking the web interface.

The app will automatically:

- Start the server
- Open your browser to http://localhost:8080

### Development Options

```bash
# Run with a different port
./run-app.sh -p 5000

# Run in debug mode
./run-app.sh -d

# Check dependencies
./check-dependencies.sh

# Run worker with custom Redis URL
REDIS_URL=redis://custom-host:6379 python worker_simple.py
```

## Environment Variables

The application can be configured using environment variables in a `.env` file:

```
# Flask configuration
FLASK_ENV=development
FLASK_DEBUG=0
FLASK_HOST=0.0.0.0
FLASK_PORT=8080

# Redis and background jobs
REDIS_URL=redis://localhost:6379

# Scraper configuration
MAX_FETCH_LIMIT=300
REQUEST_TIMEOUT=20
MAX_RETRIES=3
CACHE_EXPIRY=86400
RATE_LIMIT_RPM=30
YOUTUBE_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
```

See `.env.example` for all available options.

## Deployment to Railway

This application can be easily deployed on Railway. Follow these steps:

1.  Sign up for a Railway account at [railway.app](https://railway.app) if you don't have one.
2.  Create a new project on Railway and choose "Deploy from GitHub repo".
3.  Connect your GitHub account and select this repository.
4.  Railway will automatically detect the `Procfile` and `requirements.txt`. It will build and deploy your application.
5.  **Configure Environment Variables:** Go to your service settings in the Railway dashboard. Under the "Variables" tab, add the necessary environment variables based on your `.env.example` file. Railway injects these variables into your application's environment at runtime.
6.  Your application should now be deployed and accessible via the URL provided by Railway. Railway handles automatic deployments when you push changes to your connected branch.

### Important Notes for Railway Deployment

- Railway automatically detects the required start commands from the `Procfile`.
- The Procfile contains commands for both the web app and worker process.
- Dependencies are installed from `requirements.txt`.
- Ensure all necessary environment variables from `.env.example` are set in the Railway service variables section.
- Railway will handle running both the web app and the worker process.

## Advanced Usage

### Direct PDF Generation

You can generate PDFs directly by navigating to:

```
http://localhost:8080/direct_pdf_download?artist_name=Ben%20UFO
```

### API Endpoints

The application provides the following API endpoints:

- `/api/list?artist_name=Ben%20UFO` - Get JSON data of all tracks (synchronous, may time out for large requests)
- `/search?artist_name=Ben%20UFO` - Start a background job to fetch tracks (recommended for large requests)
- `/job/<job_id>/status` - Check status of a background job
- `/job/<job_id>/result` - Get results of a completed background job
- `/search_video?query=Artist%20-%20Track` - Search YouTube for a video
- `/start_pdf_job?artist_name=Ben%20UFO` - Start a background job to generate a PDF
- `/get_pdf/<job_id>` - Download the generated PDF from a completed job

## How It Works

1. The app scrapes DJ tracklists from [MixesDB](https://www.mixesdb.com/)
2. Background processing:
   - For large requests, the app uses a Redis queue and worker process
   - The web interface remains responsive while scraping happens in the background
   - Real-time progress updates are shown to the user
3. When you click Play, it searches YouTube for the track and plays the audio
4. For better listening experience, playback starts at 2 minutes into each track
5. If you want to view the full YouTube video, click the YouTube icon next to the player
6. PDF generation also happens in the background to prevent timeouts

## Technology Stack

- Backend: Python, Flask
- Queue System: Redis, RQ (Redis Queue)
- Worker: Python RQ SimpleWorker
- Frontend: HTML, CSS, JavaScript
- Data Processing: BeautifulSoup, requests
- PDF Generation: ReportLab
- Audio: YouTube embed API (audio-only mode)
- Data Source: MixesDB.com
- Deployment: Railway

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.
