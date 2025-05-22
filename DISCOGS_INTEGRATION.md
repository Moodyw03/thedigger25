# Discogs Label Discography Integration

This document outlines the integration of Discogs API for label discography searches in The Digger application.

## Overview

The implementation adds a separate search feature for record label discographies from Discogs without affecting the existing DJ set search feature from MixesDB.

### Key Features

1. Toggle between two search modes: DJ Sets (MixesDB) and Label Discography (Discogs)
2. Search for record labels by name
3. View a label's discography (releases)
4. Play tracks from releases using YouTube (reusing existing functionality)

## Implementation Details

### Backend Components

1. **discogs.py**: Handles all API interactions with Discogs

   - `search_labels()`: Search for labels by name
   - `get_label_releases()`: Get a label's discography
   - `get_release_details()`: Get detailed information about a specific release

2. **New API Routes in app.py**:
   - `/discogs/search_label`: Search for labels
   - `/discogs/label/<label_id>/releases`: Get a label's releases
   - `/discogs/release/<release_id>`: Get release details

### Frontend Components

1. **Search Type Toggle**: Added buttons to switch between DJ Sets and Label search
2. **Modified Search Behavior**: Form submission logic now checks search type
3. **New Rendering Functions**:
   - `renderLabelSearchResults()`: Display label search results
   - `fetchLabelDiscography()`: Load a label's discography
   - `renderLabelDiscography()`: Display a label's releases

## Configuration

Discogs API requires authentication. Set these environment variables:

```
DISCOGS_TOKEN=your_discogs_token
DISCOGS_USER_AGENT="TheDigger/1.0 +your_contact_info"
```

You can set them temporarily using the provided `setup-discogs.sh` script:

```bash
source setup-discogs.sh
```

## Usage

1. Visit the main page of The Digger
2. Select "Label Discography (Discogs)" from the toggle
3. Enter a label name (e.g., "Hessle Audio")
4. Click "Find Discography"
5. From the search results, click "View Discography" on a label
6. To play a track, click the "Play" button next to any release

## Caching

All Discogs API responses are cached if Redis is available, using the same caching system as the MixesDB integration. This helps reduce API calls and improves performance.

## Limitations

- Discogs API has rate limiting, which might affect heavy usage
- Search results are limited to prevent excessive data transfer
- YouTube search for tracks may not always find the exact release
