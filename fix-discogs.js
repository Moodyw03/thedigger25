// Fix for missing functions in the Discogs integration
// Add these functions to the script in index.html

// Function to show error messages
function showError(message) {
  const errorContainer = document.getElementById("error-container");
  if (errorContainer) {
    errorContainer.textContent = message;
    errorContainer.style.display = "block";
  }
}

// Function to hide error messages
function hideError() {
  const errorContainer = document.getElementById("error-container");
  if (errorContainer) {
    errorContainer.style.display = "none";
  }
}

// Function to clear results
function clearResults() {
  const resultsContainer = document.getElementById("results-container");
  if (resultsContainer) {
    resultsContainer.innerHTML = "";
  }
}

// Function to reset UI after error
function resetUiOnError() {
  const searchButton = document.getElementById("search-button");
  const progressIndicator = document.getElementById("progress-indicator");

  if (searchButton) {
    searchButton.disabled = false;

    // Check which search type is active and set appropriate button text
    const searchType = document.getElementById("search-type").value;
    if (searchType === "dj") {
      searchButton.textContent = "Find Tracklists";
    } else {
      searchButton.textContent = "Find Discography";
    }
  }

  if (progressIndicator) {
    progressIndicator.style.display = "none";
  }
}

// Function to poll job status for DJ sets search
function pollJobStatus(jobId) {
  const progressBar = document.getElementById("progress-bar-fill");
  const progressStatus = document.getElementById("progress-status");
  const progressIndicator = document.getElementById("progress-indicator");
  const errorContainer = document.getElementById("error-container");
  const searchButton = document.getElementById("search-button");

  let pollInterval = setInterval(() => {
    fetch(`/job/${jobId}/status`)
      .then((response) => response.json())
      .then((statusData) => {
        if (statusData.status === "finished") {
          clearInterval(pollInterval);
          if (progressBar) progressBar.style.width = "90%";
          if (progressStatus)
            progressStatus.textContent = "Fetching results...";

          // Get the job result
          return fetch(`/job/${jobId}/result`);
        } else if (statusData.status === "failed") {
          clearInterval(pollInterval);
          throw new Error(
            `Job failed: ${
              (statusData.meta && statusData.meta.error) || "Unknown error"
            }`
          );
        } else {
          // Update progress
          const progress = (statusData.meta && statusData.meta.progress) || 0;
          if (progressBar)
            progressBar.style.width = `${Math.max(
              10,
              Math.min(80, progress)
            )}%`;
          if (progressStatus)
            progressStatus.textContent =
              (statusData.meta && statusData.meta.status) || "Processing...";
        }
      })
      .then((response) => {
        if (response) return response.json();
      })
      .then((resultData) => {
        if (resultData) {
          if (progressBar) progressBar.style.width = "100%";
          if (progressStatus) progressStatus.textContent = "Search complete!";

          setTimeout(() => {
            if (progressIndicator) progressIndicator.style.display = "none";
          }, 1000);

          renderResults(resultData.data);
          if (searchButton) {
            searchButton.disabled = false;
            searchButton.textContent = "Find Tracklists";
          }
        }
      })
      .catch((error) => {
        clearInterval(pollInterval);
        console.error("Polling error:", error);
        if (errorContainer) {
          errorContainer.textContent = `Error: ${error.message}`;
          errorContainer.style.display = "block";
        }
        if (progressIndicator) progressIndicator.style.display = "none";
        if (searchButton) {
          searchButton.disabled = false;
          searchButton.textContent = "Find Tracklists";
        }
      });
  }, 2000); // Poll every 2 seconds
}

// Function to render DJ set results
function renderResults(data) {
  const resultsContainer = document.getElementById("results-container");
  if (!resultsContainer) return;

  // Check if we have the right data structure
  const mixes = data.mixes || data;
  const artistName = data.artist || "";

  if (!mixes || mixes.length === 0) {
    resultsContainer.innerHTML =
      '<div class="no-results">No mixes found for this artist.</div>';
    return;
  }

  // Sort mixes by date if available (newest first)
  const sortedMixes = [...mixes].sort((a, b) => {
    if (a.date && b.date) {
      return new Date(b.date) - new Date(a.date);
    }
    return 0;
  });

  // Build results HTML
  let html = `
        <h2>DJ Sets by ${artistName || "Artist"}</h2>
        <div class="mixes-container">
    `;

  // Add mixes to the HTML
  sortedMixes.forEach((mix) => {
    const date = mix.date ? `<span class="mix-date">${mix.date}</span>` : "";
    const hasTracklist = mix.has_tracklist ? "has-tracklist" : "no-tracklist";
    const trackCount = mix.tracks ? mix.tracks.length : 0;

    html += `
            <div class="mix-item ${hasTracklist}" data-mix-id="${mix.id || ""}">
                <div class="mix-header">
                    <h3 class="mix-title">${mix.title || "Untitled Mix"}</h3>
                    ${date}
                </div>
                <div class="mix-details">
                    <span class="track-count">${trackCount} tracks</span>
                    <button class="view-tracklist-btn" data-mix-index="${sortedMixes.indexOf(
                      mix
                    )}">
                        View Tracklist
                    </button>
                </div>
            </div>
        `;
  });

  html += `
        </div>
        <div id="tracklist-viewer" style="display: none;">
            <div class="tracklist-header">
                <h3 id="current-mix-title"></h3>
                <button id="close-tracklist">Close Tracklist</button>
            </div>
            <div id="tracklist-container"></div>
        </div>
    `;

  resultsContainer.innerHTML = html;

  // Add event listeners to tracklist buttons
  document.querySelectorAll(".view-tracklist-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const mixIndex = parseInt(this.dataset.mixIndex);
      const mix = sortedMixes[mixIndex];

      // Display the tracklist
      const tracklistViewer = document.getElementById("tracklist-viewer");
      const currentMixTitle = document.getElementById("current-mix-title");
      const tracklistContainer = document.getElementById("tracklist-container");

      if (tracklistViewer && currentMixTitle && tracklistContainer) {
        // Set mix title
        currentMixTitle.textContent = mix.title || "Untitled Mix";

        // Build tracklist HTML
        let tracklistHtml = "";

        if (mix.tracks && mix.tracks.length > 0) {
          tracklistHtml = '<ul class="track-list">';

          mix.tracks.forEach((track, index) => {
            tracklistHtml += `
                            <li class="track-item">
                                <div class="track-item-content">
                                    <div class="track-info">
                                        <span class="track-number">${
                                          index + 1
                                        }.</span>
                                        <span class="track-name">${
                                          track.artist
                                            ? track.artist + " - "
                                            : ""
                                        }${
              track.title || "Unknown Track"
            }</span>
                                    </div>
                                    <div class="track-actions">
                                        <button class="play-button" data-query="${encodeURIComponent(
                                          `${track.artist || ""} ${
                                            track.title || "Unknown Track"
                                          }`
                                        )}">
                                            <span class="play-icon">▶</span> Play
                                        </button>
                                    </div>
                                </div>
                            </li>
                        `;
          });

          tracklistHtml += "</ul>";
        } else {
          tracklistHtml =
            '<p class="no-tracks">No tracklist available for this mix.</p>';
        }

        // Set tracklist content
        tracklistContainer.innerHTML = tracklistHtml;

        // Show the tracklist
        tracklistViewer.style.display = "block";

        // Add event listeners to play buttons
        document.querySelectorAll(".play-button").forEach((playButton) => {
          playButton.addEventListener("click", function () {
            const query = this.dataset.query;
            searchYouTube(query);
          });
        });
      }
    });
  });

  // Add event listener to close tracklist button
  const closeTracklistButton = document.getElementById("close-tracklist");
  if (closeTracklistButton) {
    closeTracklistButton.addEventListener("click", function () {
      const tracklistViewer = document.getElementById("tracklist-viewer");
      if (tracklistViewer) {
        tracklistViewer.style.display = "none";
      }
    });
  }
}
