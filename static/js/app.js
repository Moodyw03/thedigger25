// App initialization logic
document.addEventListener("DOMContentLoaded", function () {
  // Initialize global variables
  const errorContainer = document.getElementById("error-container");
  const resultsContainer = document.getElementById("results-container");

  // Set up search source buttons
  const searchForm = document.getElementById("search-form");
  const searchSourceInput = document.getElementById("search-source");
  const sourceButtons = document.querySelectorAll(".source-button");

  // Add click event listeners to source buttons
  sourceButtons.forEach((button) => {
    button.addEventListener("click", function () {
      // Remove active class from all buttons
      sourceButtons.forEach((btn) => btn.classList.remove("active"));
      // Add active class to clicked button
      this.classList.add("active");
      // Update hidden input with source value
      searchSourceInput.value = this.dataset.source;
      console.log(`Search source set to: ${searchSourceInput.value}`);
    });
  });

  // Form submission handler
  if (searchForm) {
    searchForm.addEventListener("submit", function (e) {
      e.preventDefault(); // Prevent standard form submission

      const query = document.getElementById("search-input").value.trim();
      const source = searchSourceInput.value;

      if (!query) {
        if (errorContainer) {
          errorContainer.textContent = "Please enter a search term";
          errorContainer.style.display = "block";
        }
        return;
      }

      // Show progress indicator
      const progressIndicator = document.getElementById("progress-indicator");
      const progressBar = document.getElementById("progress-bar-fill");
      const progressStatus = document.getElementById("progress-status");

      if (progressIndicator) progressIndicator.style.display = "block";
      if (errorContainer) errorContainer.style.display = "none";
      if (progressBar) progressBar.style.width = "10%";
      if (progressStatus)
        progressStatus.textContent = `Starting ${source} search...`;

      // Clear previous results
      if (resultsContainer) resultsContainer.innerHTML = "";

      // Create form data for submission
      const formData = new FormData();
      formData.append("query", query);
      formData.append("source", source);

      // Perform AJAX request
      fetch("/search_combined", {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          if (progressBar) progressBar.style.width = "50%";
          if (progressStatus)
            progressStatus.textContent = "Processing results...";

          if (data.status === "cached") {
            console.log("Using cached results");
            // Handle MixesDB cached results
            if (source === "mixesdb") {
              handleMixesDBResults(data.data);
            } else {
              // Handle Discogs cached results
              handleDiscogsResults(data.data);
            }
            if (progressIndicator) progressIndicator.style.display = "none";
          } else if (data.job_id) {
            // Poll for job status and results
            pollJobStatus(data.job_id, source);
          } else {
            throw new Error("Invalid response from server");
          }
        })
        .catch((error) => {
          console.error("Search error:", error);
          if (errorContainer) {
            errorContainer.textContent = `Search error: ${error.message}`;
            errorContainer.style.display = "block";
          }
          if (progressIndicator) progressIndicator.style.display = "none";
        });
    });
  }

  // Function to poll for job status
  function pollJobStatus(jobId, source) {
    const progressBar = document.getElementById("progress-bar-fill");
    const progressStatus = document.getElementById("progress-status");
    const progressIndicator = document.getElementById("progress-indicator");

    let pollInterval = setInterval(() => {
      fetch(`/job/${jobId}/status`)
        .then((response) => response.json())
        .then((statusData) => {
          if (statusData.state === "finished") {
            clearInterval(pollInterval);
            if (progressBar) progressBar.style.width = "90%";
            if (progressStatus)
              progressStatus.textContent = "Fetching results...";

            // Get the job result
            return fetch(`/job/${jobId}/result`);
          } else if (statusData.state === "failed") {
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

            // Handle results based on source
            if (source === "mixesdb") {
              handleMixesDBResults(resultData);
            } else {
              handleDiscogsResults(resultData);
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
        });
    }, 2000); // Poll every 2 seconds
  }

  // Handle MixesDB results
  function handleMixesDBResults(data) {
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

    sortedMixes.forEach((mix) => {
      html += `
                <div class="mix">
                    <h3>${mix.title || "Untitled Mix"} <span class="mix-date">${
        mix.date || ""
      }</span></h3>
            `;

      if (mix.tracklist && mix.tracklist.length >= 1) {
        html += `<div class="tracklist-container">
                    <h4 class="tracklist-header">Tracklist (${mix.tracklist.length} tracks)</h4>
                    <ul class="track-list">`;

        mix.tracklist.forEach((track, index) => {
          // Track can be either an object with track property, or just a string
          const trackName = track.track || track;
          const trackId = track.id || `track-${index}`;

          html += `
                        <li class="track-item" data-track-name="${trackName}">
                            <div class="track-item-content">
                                <div class="track-info">
                                    <span class="track-number">${
                                      index + 1
                                    }.</span>
                                    <span class="track-name">${trackName}</span>
                                </div>
                                <div class="track-actions">
                                    <button class="play-button">
                                        <span class="play-icon">▶</span> PLAY
                                    </button>
                                </div>
                            </div>
                            <div class="inline-player-container">
                                <div class="youtube-player-wrapper" id="player-${trackId}"></div>
                                <div class="audio-controls">
                                    <span class="time-display">0:00 / 0:00</span>
                                </div>
                                <div class="player-error">
                                    <span class="player-error-icon">⚠</span>
                                    <span class="player-error-message"></span>
                                </div>
                            </div>
                        </li>
                    `;
        });

        html += `</ul></div>`;
      } else {
        html += `<p class="no-tracklist">No tracklist available for this mix.</p>`;
      }

      html += `</div>`;
    });

    html += `</div>`;
    resultsContainer.innerHTML = html;

    // Initialize play buttons for the tracks
    if (typeof setupPlayButtons === "function") {
      setupPlayButtons(resultsContainer);
    } else {
      console.error("setupPlayButtons function not available");
    }

    // Add toggle functionality for tracklists
    document.querySelectorAll(".tracklist-header").forEach((header) => {
      header.addEventListener("click", function () {
        this.classList.toggle("collapsed");
      });
    });
  }

  // Handle Discogs results
  function handleDiscogsResults(data) {
    if (!resultsContainer) return;

    // Different handling based on what type of results we got
    if (data.artists) {
      // Artist search results
      displayDiscogsArtistResults(data.artists);
    } else if (data.labels) {
      // Label search results
      displayDiscogsLabelResults(data.labels);
    } else if (data.releases) {
      // Releases (either from artist or label)
      displayDiscogsReleases(
        data.releases,
        data.artist_name || data.label_name
      );
    } else {
      resultsContainer.innerHTML =
        '<div class="no-results">No results found.</div>';
    }
  }

  function displayDiscogsArtistResults(artists) {
    if (!artists || artists.length === 0) {
      resultsContainer.innerHTML =
        '<div class="no-results">No artists found.</div>';
      return;
    }

    let html = `
            <h2>Artists</h2>
            <div class="discogs-results">
        `;

    artists.forEach((artist) => {
      const thumb = artist.thumb || "/static/images/default-artist.png";

      html += `
                <div class="discogs-result">
                    <img src="${thumb}" alt="${
        artist.name
      }" class="discogs-thumb">
                    <div class="discogs-info">
                        <div class="discogs-title">${artist.name}</div>
                        <div class="discogs-subtitle">${
                          artist.profile || ""
                        }</div>
                        <div class="discogs-meta">
                            ${
                              artist.country
                                ? `<span class="discogs-meta-item">${artist.country}</span>`
                                : ""
                            }
                            ${
                              artist.year
                                ? `<span class="discogs-meta-item">${artist.year}</span>`
                                : ""
                            }
                        </div>
                        <div class="discogs-actions">
                            <button class="discogs-button view-releases" data-artist-id="${
                              artist.id
                            }">View Releases</button>
                            <button class="discogs-button search-youtube" data-artist-name="${
                              artist.name
                            }">YouTube Search</button>
                        </div>
                    </div>
                </div>
            `;
    });

    html += `</div>`;
    resultsContainer.innerHTML = html;

    // Add event listeners for the action buttons
    document.querySelectorAll(".view-releases").forEach((button) => {
      button.addEventListener("click", function () {
        const artistId = this.dataset.artistId;
        fetchArtistReleases(artistId);
      });
    });

    document.querySelectorAll(".search-youtube").forEach((button) => {
      button.addEventListener("click", function () {
        const artistName = this.dataset.artistName;
        window.open(
          `https://www.youtube.com/results?search_query=${encodeURIComponent(
            artistName
          )}&autoplay=1`,
          "_blank"
        );
      });
    });
  }

  function displayDiscogsLabelResults(labels) {
    if (!labels || labels.length === 0) {
      resultsContainer.innerHTML =
        '<div class="no-results">No labels found.</div>';
      return;
    }

    let html = `
            <h2>Labels</h2>
            <div class="discogs-results">
        `;

    labels.forEach((label) => {
      const thumb = label.thumb || "/static/images/default-label.png";

      html += `
                <div class="discogs-result">
                    <img src="${thumb}" alt="${
        label.name
      }" class="discogs-thumb">
                    <div class="discogs-info">
                        <div class="discogs-title">${label.name}</div>
                        <div class="discogs-subtitle">${
                          label.profile || ""
                        }</div>
                        <div class="discogs-meta">
                            ${
                              label.country
                                ? `<span class="discogs-meta-item">${label.country}</span>`
                                : ""
                            }
                            ${
                              label.year
                                ? `<span class="discogs-meta-item">${label.year}</span>`
                                : ""
                            }
                        </div>
                        <div class="discogs-actions">
                            <button class="discogs-button view-releases" data-label-id="${
                              label.id
                            }">View Releases</button>
                            <button class="discogs-button search-youtube" data-label-name="${
                              label.name
                            }">YouTube Search</button>
                        </div>
                    </div>
                </div>
            `;
    });

    html += `</div>`;
    resultsContainer.innerHTML = html;

    // Add event listeners for the action buttons
    document.querySelectorAll(".view-releases").forEach((button) => {
      button.addEventListener("click", function () {
        const labelId = this.dataset.labelId;
        fetchLabelReleases(labelId);
      });
    });

    document.querySelectorAll(".search-youtube").forEach((button) => {
      button.addEventListener("click", function () {
        const labelName = this.dataset.labelName;
        window.open(
          `https://www.youtube.com/results?search_query=${encodeURIComponent(
            labelName
          )}&autoplay=1`,
          "_blank"
        );
      });
    });
  }

  function displayDiscogsReleases(releases, entityName) {
    if (!releases || releases.length === 0) {
      resultsContainer.innerHTML =
        '<div class="no-results">No releases found.</div>';
      return;
    }

    let html = `
            <h2>Releases by ${entityName || "Artist/Label"}</h2>
            <div class="discogs-releases">
        `;

    releases.forEach((release) => {
      const thumb = release.thumb || "/static/images/default-release.png";
      const tracklist = release.tracklist || [];

      html += `
                <div class="discogs-result">
                    <img src="${thumb}" alt="${
        release.title
      }" class="discogs-thumb">
                    <div class="discogs-info">
                        <div class="discogs-title">${release.title}</div>
                        <div class="discogs-subtitle">${
                          release.artist || ""
                        } - ${release.year || ""}</div>
                        <div class="discogs-meta">
                            ${
                              release.format
                                ? `<span class="discogs-meta-item">${release.format}</span>`
                                : ""
                            }
                            ${
                              release.label
                                ? `<span class="discogs-meta-item">${release.label}</span>`
                                : ""
                            }
                            ${
                              release.country
                                ? `<span class="discogs-meta-item">${release.country}</span>`
                                : ""
                            }
                        </div>
            `;

      if (tracklist && tracklist.length > 0) {
        html += `
                    <div class="discogs-actions">
                        <button class="discogs-button toggle-tracklist" data-release-id="${release.id}">Show Tracklist</button>
                        <button class="discogs-button search-youtube" data-release-title="${release.artist} ${release.title}">YouTube Search</button>
                    </div>
                    <div class="release-tracklist" id="tracklist-${release.id}" style="display: none;">
                        <ul class="track-list">
                `;

        tracklist.forEach((track, index) => {
          const trackName = track.artist
            ? `${track.artist} - ${track.title}`
            : track.title;
          const trackId = `track-${release.id}-${index}`;

          html += `
                        <li class="track-item" data-track-name="${trackName}">
                            <div class="track-item-content">
                                <div class="track-info">
                                    <span class="track-number">${
                                      track.position || index + 1
                                    }.</span>
                                    <span class="track-name">${trackName}</span>
                                </div>
                                <div class="track-actions">
                                    <button class="play-button">
                                        <span class="play-icon">▶</span> PLAY
                                    </button>
                                </div>
                            </div>
                            <div class="inline-player-container">
                                <div class="youtube-player-wrapper" id="player-${trackId}"></div>
                                <div class="audio-controls">
                                    <span class="time-display">0:00 / 0:00</span>
                                </div>
                                <div class="player-error">
                                    <span class="player-error-icon">⚠</span>
                                    <span class="player-error-message"></span>
                                </div>
                            </div>
                        </li>
                    `;
        });

        html += `
                        </ul>
                    </div>
                `;
      } else {
        html += `
                    <div class="discogs-actions">
                        <button class="discogs-button search-youtube" data-release-title="${release.artist} ${release.title}">YouTube Search</button>
                    </div>
                    <p class="no-tracklist">No tracklist available for this release.</p>
                `;
      }

      html += `
                    </div>
                </div>
            `;
    });

    html += `</div>`;
    resultsContainer.innerHTML = html;

    // Add event listeners for toggle tracklist buttons
    document.querySelectorAll(".toggle-tracklist").forEach((button) => {
      button.addEventListener("click", function () {
        const releaseId = this.dataset.releaseId;
        const tracklistDiv = document.getElementById(`tracklist-${releaseId}`);

        if (tracklistDiv) {
          const isVisible = tracklistDiv.style.display !== "none";
          tracklistDiv.style.display = isVisible ? "none" : "block";
          this.textContent = isVisible ? "Show Tracklist" : "Hide Tracklist";

          // Initialize play buttons if showing tracklist
          if (!isVisible && typeof setupPlayButtons === "function") {
            setupPlayButtons(tracklistDiv);
          }
        }
      });
    });

    // Add event listeners for YouTube search buttons
    document.querySelectorAll(".search-youtube").forEach((button) => {
      button.addEventListener("click", function () {
        const searchTerm = this.dataset.releaseTitle;
        window.open(
          `https://www.youtube.com/results?search_query=${encodeURIComponent(
            searchTerm
          )}&autoplay=1`,
          "_blank"
        );
      });
    });
  }

  function fetchArtistReleases(artistId) {
    // Show loading state
    if (resultsContainer) {
      resultsContainer.innerHTML =
        '<div class="loading">Loading releases...</div>';
    }

    fetch(`/artist_releases/${artistId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.job_id) {
          // Poll for job status and results for artist releases
          pollJobStatus(data.job_id, "discogs-artist");
        } else {
          throw new Error("Invalid response from server");
        }
      })
      .catch((error) => {
        console.error("Error fetching artist releases:", error);
        if (resultsContainer) {
          resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        }
      });
  }

  function fetchLabelReleases(labelId) {
    // Show loading state
    if (resultsContainer) {
      resultsContainer.innerHTML =
        '<div class="loading">Loading releases...</div>';
    }

    fetch(`/label_releases/${labelId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.job_id) {
          // Poll for job status and results for label releases
          pollJobStatus(data.job_id, "discogs-label");
        } else {
          throw new Error("Invalid response from server");
        }
      })
      .catch((error) => {
        console.error("Error fetching label releases:", error);
        if (resultsContainer) {
          resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        }
      });
  }
});
