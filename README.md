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
./run-app.sh
```

The app will automatically:

- Start the server
- Open your browser to http://localhost:8080

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
