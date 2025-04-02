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

5. Run the application

```bash
# Option 1: Using the shell script (recommended)
./run-app.sh

# Option 2: Direct Python command
python digger.py

# Option 3: If you've set up the alias using reset-terminal.sh
digger
```

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
```

## Environment Variables

The application can be configured using environment variables in a `.env` file:

```
FLASK_ENV=development
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

- Railway automatically detects the required start command from the `Procfile`.
- Dependencies are installed from `requirements.txt`.
- Ensure all necessary environment variables from `.env.example` are set in the Railway service variables section.

## Advanced Usage

### Direct PDF Generation

You can generate PDFs directly by navigating to:

```
http://localhost:8080/direct_pdf_download?artist_name=Ben%20UFO
```

### API Endpoints

The application provides the following API endpoints:

- `/api/list?artist_name=Ben%20UFO` - Get JSON data of all tracks
- `/search_video?query=Artist%20-%20Track` - Search YouTube for a video
- `/download_tracklists_pdf?artist_name=Ben%20UFO` - Generate a PDF of tracklists

## How It Works

1. The app scrapes DJ tracklists from [MixesDB](https://www.mixesdb.com/)
2. When you click Play, it searches YouTube for the track and plays the audio
3. For better listening experience, playback starts at 2 minutes into each track
4. If you want to view the full YouTube video, click the YouTube icon next to the player

## Technology Stack

- Backend: Python, Flask
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
