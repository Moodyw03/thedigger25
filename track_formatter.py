def format_track_for_pdf(track):
    """Format track data for PDF display, handling both string and dictionary formats."""
    # If track is already a string, just return it
    if isinstance(track, str):
        return track
    # If track is a dictionary, extract the track field
    if isinstance(track, dict) and "track" in track:
        return track["track"]
    # Fallback to string representation if all else fails
    try:
        if isinstance(track, dict):
            # Try to format nicely based on common fields
            if "id" in track and track["id"]:
                return track["id"]  # The ID is usually a cleaned version of the track
        # If we get here, convert to string but clean it up
        track_str = str(track)
        # Remove common dict formatting characters
        track_str = track_str.replace('{', '').replace('}', '').replace("'", '')
        track_str = track_str.replace("track:", "").replace("id:", "")
        return track_str
    except:
        # Last resort
        return "Unknown track format"
