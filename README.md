# The Digger

A tool for finding and listening to tracks played by your favorite DJs on MixesDB.

## Features

- Search for any DJ/artist on MixesDB
- View all tracks they've played in their sets
- Listen to tracks directly in the app (audio-only, starting at 2 minutes)
- Minimal, clean interface
- YouTube link to open full videos when needed

## Running the App

This application is now a single integrated package - both the backend and frontend are bundled together.

### Quick Start

1. Make sure you have Python 3.x installed
2. Clone this repository

```bash
git clone https://github.com/Moodyw03/thedigger25.git
cd thedigger25
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
# Option 1: Using the shell script
./run-app.sh

# Option 2: Direct Python command
python app.py

# Option 3: If you've set up the alias using reset-terminal.sh
digger
```

The app will automatically:

- Start the server
- Open your browser to http://localhost:8080

### Development Commands

```bash
# Run tests (if implemented)
pytest

# Check code style
flake8

# Run with debug mode enabled
export FLASK_DEBUG=1
python app.py
```

## Deployment to Vercel

This application is optimized for deployment on Vercel. Follow these steps to deploy:

1. Sign up for a Vercel account at [vercel.com](https://vercel.com) if you don't have one
2. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```
3. Login to Vercel:
   ```bash
   vercel login
   ```
4. Deploy the application:
   ```bash
   vercel
   ```
5. For production deployment:
   ```bash
   vercel --prod
   ```

### Vercel Optimizations

This application includes several optimizations for running on Vercel's serverless platform:

1. **In-memory caching** for YouTube video searches and web requests to reduce API calls
2. **Exponential backoff with jitter** for retry attempts to improve reliability
3. **Environment variables** for configuration:
   - `FLASK_ENV`: Set to "production" for production deployment
   - `MAX_FETCH_LIMIT`: Maximum number of items to fetch (default: 300)
   - `REQUEST_TIMEOUT`: Timeout for HTTP requests in seconds (default: 20)
   - `MAX_RETRIES`: Number of retry attempts for HTTP requests (default: 3)
   - `CACHE_EXPIRY`: Cache expiry time in seconds (default: 86400 - 24 hours)
   - `YOUTUBE_USER_AGENT`: Custom user agent for YouTube requests

### Important Notes for Vercel Deployment

- Serverless functions on Vercel have a maximum execution time (10 seconds on free tier)
- Web scraping operations might time out if they take too long
- Consider upgrading to Vercel Pro if you need longer function execution times
- The application uses caching to reduce API calls and improve performance

## Important Note

**The separate `the-digger-ui` repository is no longer needed.** The UI has been fully integrated into this project.

If you still have the separate UI repository, you can safely remove it by running:

```bash
./reset-terminal.sh
```

This script will:

- Remove the old UI repository if it exists
- Add a convenient `digger` alias to your shell
- Reset any terminal settings that might be causing prompts

After running the script, simply restart your terminal, and you can run the app by typing `digger` from anywhere.

## How It Works

1. The app scrapes DJ tracklists from [MixesDB](https://www.mixesdb.com/)
2. When you click Play, it searches YouTube for the track and plays the audio
3. For better listening experience, playback starts at 2 minutes into each track
4. If you want to view the full YouTube video, click the YouTube icon next to the player

## Technology Stack

- Backend: Python, Flask
- Frontend: HTML, CSS, JavaScript
- Audio: YouTube embed API (audio-only mode)
- Data Source: MixesDB.com
