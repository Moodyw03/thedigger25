import re

# Read the file
with open('templates/index.html', 'r') as f:
    content = f.read()

# Remove the play track button from the tracklist in the release modal
pattern = re.compile(r'<button class="play-track-btn"[^>]*?data-query="\${encodeURIComponent\(`\${trackArtist} - \${track\.title}`\)}".*?</button>', re.DOTALL)
modified = pattern.sub('', content)

# Write modified content back
with open('templates/index.html', 'w') as f:
    f.write(modified)

print('Play track button removed from release modal tracklist') 