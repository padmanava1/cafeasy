/**
 * Cafeasy - Client Application Logic
 * Integrates Chat UI, Leaflet GIS Map, Geolocation, Live Route Polyline, and FastAPI RAG Endpoints.
 */

// Global State
let map;
let allMarkers = {};
let activeMarkerLayer;
let userMarker = null;
let currentRouteLayer = null;
let userLocation = null; // { lat, lng }
const AHMEDABAD_CENTER = [23.0338, 72.5363]; // Central Ahmedabad (Vastrapur / Bodakdev)

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  checkSystemHealth();
  setupEventListeners();
  // Proactively try to locate user if permission already granted
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserPosition(pos.coords.latitude, pos.coords.longitude, false),
      (err) => console.log("Proactive geolocation deferred:", err.message),
      { timeout: 5000 }
    );
  }
});

/**
 * 1. Initialize Interactive Leaflet Map
 */
function initMap() {
  map = L.map("map", {
    center: AHMEDABAD_CENTER,
    zoom: 13,
    zoomControl: false,
    preferCanvas: true
  });

  // Position zoom control on bottom-right
  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Base Layer 1: Standard OpenStreetMap (always reliable, never blocked)
  const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    subdomains: ['a', 'b', 'c'],
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  });

  // Base Layer 2: CartoDB Voyager (aesthetic street map)
  const cartoLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    subdomains: ['a', 'b', 'c', 'd'],
    attribution: '&copy; OpenStreetMap &copy; CARTO'
  });

  // Add OSM as default
  osmLayer.addTo(map);

  // Add base layer selector so user can easily toggle
  L.control.layers({
    "OpenStreetMap (Standard)": osmLayer,
    "Carto Voyager (Modern)": cartoLayer
  }, null, { position: "topright" }).addTo(map);

  activeMarkerLayer = L.layerGroup().addTo(map);

  // Universal fix for Leaflet in CSS flex layouts: force recalculate tile viewports
  [100, 300, 600, 1000].forEach(delay => {
    setTimeout(() => {
      if (map) map.invalidateSize();
    }, delay);
  });

  window.addEventListener("resize", () => {
    if (map) map.invalidateSize();
  });

  const mapSection = document.querySelector(".map-section");
  if (mapSection && window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      if (map) map.invalidateSize();
    });
    ro.observe(mapSection);
  }
}

/**
 * 2. Geolocation / User Location Handling
 */
function locateUser(centerMap = true) {
  const btn = document.getElementById("locateBtn");
  const label = document.getElementById("locateBtnLabel");

  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return;
  }

  label.innerText = "Locating...";
  btn.classList.add("loading");

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      setUserPosition(pos.coords.latitude, pos.coords.longitude, centerMap);
      btn.classList.remove("loading");
      btn.classList.add("active");
      label.innerText = "Located";
    },
    (err) => {
      btn.classList.remove("loading");
      label.innerText = "Locate Me";
      console.warn("Geolocation error:", err);
      // Friendly simulation if browser blocks GPS locally
      const simulatedLat = 23.0378;
      const simulatedLng = 23.0378 ? 72.5120 : 72.5363; // Bodakdev area
      const confirmSim = confirm(
        "Could not detect your exact GPS (often blocked on localhost). Would you like to use Ahmedabad (Bodakdev) as your simulated location to test navigation & distance?"
      );
      if (confirmSim) {
        setUserPosition(simulatedLat, simulatedLng, centerMap);
        btn.classList.add("active");
        label.innerText = "Bodakdev (Simulated)";
      }
    },
    { enableHighAccuracy: true, timeout: 8000 }
  );
}

function setUserPosition(lat, lng, centerMap = true) {
  userLocation = { lat, lng };

  // Remove existing user marker if present
  if (userMarker) {
    map.removeLayer(userMarker);
  }

  const userIcon = L.divIcon({
    className: "user-gps-wrapper",
    html: `<div class="user-gps-marker" title="Your Location"><i class="fa-solid fa-person"></i></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  });

  userMarker = L.marker([lat, lng], {
    icon: userIcon,
    zIndexOffset: 2000
  }).addTo(map);

  userMarker.bindPopup(`
    <div class="popup-card">
      <h4 style="color: #60a5fa;"><i class="fa-solid fa-location-crosshairs"></i> Your Location</h4>
      <p>GPS: ${lat.toFixed(4)}, ${lng.toFixed(4)}</p>
      <p style="font-size: 0.75rem; color: #94a3b8;">Cafes will calculate live driving distances from here!</p>
    </div>
  `);

  if (centerMap) {
    map.invalidateSize();
    map.flyTo([lat, lng], 14, { animate: true, duration: 1.2 });
    setTimeout(() => userMarker.openPopup(), 1200);
  }
}

/**
 * 3. Draw Driving Route via OSRM (Free OpenStreetMap Routing Engine)
 */
async function drawDrivingRoute(destLat, destLng, cafeId) {
  if (window.innerWidth <= 850) {
    switchMobileTab('map');
  }

  if (!userLocation) {
    locateUser(false);
    if (!userLocation) {
      alert("Please click 'Locate Me' first to get your start location for turn-by-turn routing!");
      return;
    }
  }

  // Remove existing route line
  if (currentRouteLayer) {
    map.removeLayer(currentRouteLayer);
    currentRouteLayer = null;
  }

  const url = `https://router.project-osrm.org/route/v1/driving/${userLocation.lng},${userLocation.lat};${destLng},${destLat}?overview=full&geometries=geojson`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Routing service unavailable");
    const data = await res.json();

    if (data.routes && data.routes.length > 0) {
      const route = data.routes[0];
      const distanceKm = (route.distance / 1000).toFixed(1);
      const durationMin = Math.round(route.duration / 60);

      const routeGeoJSON = route.geometry;
      currentRouteLayer = L.geoJSON(routeGeoJSON, {
        style: {
          color: "#3b82f6",
          weight: 5,
          opacity: 0.85,
          dashArray: "1, 8",
          lineCap: "round"
        }
      }).addTo(map);

      // Fit map to show both user and destination
      map.fitBounds(currentRouteLayer.getBounds(), { padding: [50, 50] });

      const targetMarker = allMarkers[cafeId];
      if (targetMarker) {
        targetMarker.bindPopup(`
          <div class="popup-card">
            <h4>${targetMarker.getPopup() ? targetMarker.getPopup().getContent().split('<h4>')[1].split('</h4>')[0] : 'Destination'}</h4>
            <p>🚗 <strong>${distanceKm} km</strong> • ~${durationMin} mins drive</p>
            <a href="https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=${destLat},${destLng}&travelmode=driving" 
               target="_blank" rel="noopener noreferrer" class="popup-btn">
              <i class="fa-solid fa-diamond-turn-right"></i> Open in Google Maps
            </a>
          </div>
        `).openPopup();
      }
    }
  } catch (err) {
    console.warn("Could not draw OSRM route:", err);
    // Fallback: Just fly to destination and open Google Maps
    flyToCafe(cafeId, destLat, destLng);
  }
}

/**
 * 4. Check Backend Health
 */
async function checkSystemHealth() {
  const statusElem = document.getElementById("systemStatus");
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      const data = await res.json();
      statusElem.innerHTML = `
        <span class="status-dot"></span>
        <span class="status-label">${data.indexed_cafes} Venues Indexed • ${data.llm_engine}</span>
      `;
    } else {
      statusElem.innerHTML = `<span class="status-label" style="color: #f87171;">API Initializing</span>`;
    }
  } catch (err) {
    statusElem.innerHTML = `<span class="status-label" style="color: #f87171;">Offline</span>`;
  }
}

function createCustomMarkerIcon(isActive = false, index = null) {
  const numLabel = index !== null ? `<span class="marker-num">${index}</span>` : `<i class="fa-solid fa-mug-hot"></i>`;
  return L.divIcon({
    className: "custom-marker-wrapper",
    html: `
      <div class="custom-cafe-marker ${isActive ? 'active-pin' : ''}">
        ${numLabel}
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32]
  });
}

function highlightRecommendedMarkers(geoPoints) {
  activeMarkerLayer.clearLayers();
  allMarkers = {};
  const bounds = [];

  // Hide initial map hint banner once recommendations arrive
  const hintElem = document.getElementById("mapInitialHint");
  if (hintElem) {
    hintElem.style.display = "none";
  }

  if (userLocation) {
    bounds.push([userLocation.lat, userLocation.lng]);
  }

  geoPoints.forEach((point, idx) => {
    const marker = L.marker([point.lat, point.lng], {
      icon: createCustomMarkerIcon(true, idx + 1),
      zIndexOffset: 1000 + idx
    });

    const distInfo = point.distance_km ? `🚗 ${point.distance_km} km away • ` : '';
    const navLink = point.navigation_url || point.google_maps_url;

    const popupContent = `
      <div class="popup-card">
        <h4>${idx + 1}. ${escapeHtml(point.name)}</h4>
        <p><strong>${escapeHtml(point.area)}</strong> • ${distInfo}⭐ ${point.rating} • ₹${point.price_for_two} for 2</p>
        <p><em>${point.tags ? point.tags.slice(0, 3).map(escapeHtml).join(', ') : ''}</em></p>
        <div style="display: flex; gap: 8px; margin-top: 8px;">
          <button onclick="drawDrivingRoute(${point.lat}, ${point.lng}, '${point.id}')" class="popup-btn popup-btn-route">
            <i class="fa-solid fa-route"></i> Route
          </button>
          <a href="${navLink}" target="_blank" rel="noopener noreferrer" class="popup-btn popup-btn-gmaps">
            <i class="fa-solid fa-diamond-turn-right"></i> Google Maps
          </a>
        </div>
      </div>
    `;
    marker.bindPopup(popupContent);
    marker.addTo(activeMarkerLayer);
    bounds.push([point.lat, point.lng]);

    allMarkers[point.id] = marker;
  });

  if (bounds.length > 0) {
    map.invalidateSize();
    map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
  }

  // Update mobile tab badge count
  const pinCountElem = document.getElementById("tabPinCount");
  if (pinCountElem) {
    pinCountElem.innerText = geoPoints.length;
    pinCountElem.style.display = geoPoints.length > 0 ? "inline-flex" : "none";
  }
}

/**
 * Mobile Tab Switcher Handler (For screens <= 850px)
 */
function switchMobileTab(targetTab) {
  const chatSection = document.getElementById("chatSection");
  const mapSection = document.getElementById("mapSection");
  const tabBtnChat = document.getElementById("tabBtnChat");
  const tabBtnMap = document.getElementById("tabBtnMap");

  if (targetTab === "map") {
    if (chatSection) chatSection.classList.add("tab-hidden-mobile");
    if (mapSection) mapSection.classList.add("tab-active-mobile");
    if (tabBtnChat) tabBtnChat.classList.remove("active");
    if (tabBtnMap) tabBtnMap.classList.add("active");
    if (map) {
      setTimeout(() => {
        map.invalidateSize();
      }, 100);
    }
  } else {
    if (chatSection) chatSection.classList.remove("tab-hidden-mobile");
    if (mapSection) mapSection.classList.remove("tab-active-mobile");
    if (tabBtnChat) tabBtnChat.classList.add("active");
    if (tabBtnMap) tabBtnMap.classList.remove("active");
  }
}

/**
 * 6. Event Listeners & Chat Handlers
 */
function setupEventListeners() {
  const form = document.getElementById("chatForm");
  const queryInput = document.getElementById("queryInput");
  const chips = document.querySelectorAll(".chip");
  const fitAllBtn = document.getElementById("fitAllPinsBtn");
  const locateBtn = document.getElementById("locateBtn");
  const tabBtnChat = document.getElementById("tabBtnChat");
  const tabBtnMap = document.getElementById("tabBtnMap");
  const filterBar = document.getElementById("filterBar");
  const suggestionChips = document.getElementById("suggestionChips");

  // Mouse wheel horizontal scrolling for filter bar & chips
  [filterBar, suggestionChips].forEach(el => {
    if (el) {
      el.addEventListener("wheel", (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          el.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }
  });

  if (tabBtnChat) {
    tabBtnChat.addEventListener("click", () => switchMobileTab("chat"));
  }
  if (tabBtnMap) {
    tabBtnMap.addEventListener("click", () => switchMobileTab("map"));
  }

  if (locateBtn) {
    locateBtn.addEventListener("click", () => locateUser(true));
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    submitUserQuery(query);
    queryInput.value = "";
  });

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      queryInput.value = prompt;
      submitUserQuery(prompt);
      queryInput.value = "";
    });
  });

  fitAllBtn.addEventListener("click", () => {
    if (map) map.invalidateSize();
    const allLatLngs = Object.values(allMarkers).map(m => m.getLatLng());
    if (userLocation) allLatLngs.push([userLocation.lat, userLocation.lng]);
    if (allLatLngs.length > 0) {
      map.fitBounds(allLatLngs, { padding: [50, 50], maxZoom: 15 });
    } else {
      map.flyTo(AHMEDABAD_CENTER, 13, { animate: true, duration: 1.0 });
    }
  });
}

/**
 * 7. Send User Query to FastAPI /api/chat with full multi-criteria filter payload
 */
async function submitUserQuery(query) {
  appendUserMessage(query);
  const typingId = showTypingIndicator();

  // Read filter dropdown values
  const filterArea = document.getElementById("filterArea")?.value || null;
  const filterDietary = document.getElementById("filterDietary")?.value || null;
  const filterVibe = document.getElementById("filterVibe")?.value || null;
  const filterCuisine = document.getElementById("filterCuisine")?.value || null;
  const filterBudget = document.getElementById("filterBudget")?.value ? parseInt(document.getElementById("filterBudget").value) : null;
  const filterRadius = document.getElementById("filterRadius")?.value ? parseFloat(document.getElementById("filterRadius").value) : null;
  const filterSortBy = document.getElementById("filterSortBy")?.value || "relevance";

  try {
    const payload = {
      query: query,
      area: filterArea,
      max_budget: filterBudget,
      dietary: filterDietary,
      vibe: filterVibe,
      cuisine: filterCuisine,
      sort_by: filterSortBy,
      user_lat: userLocation ? userLocation.lat : null,
      user_lng: userLocation ? userLocation.lng : null,
      max_distance_km: filterRadius
    };

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    removeTypingIndicator(typingId);

    if (!response.ok) {
      throw new Error(`Server returned error status: ${response.status}`);
    }

    const data = await response.json();
    appendAssistantResponse(data);

    // Update map with active recommendation pins
    if (data.geo_points && data.geo_points.length > 0) {
      highlightRecommendedMarkers(data.geo_points);
    }
  } catch (error) {
    removeTypingIndicator(typingId);
    appendErrorMessage("Sorry, an error occurred while generating recommendations. Please try again.");
    console.error("Chat error:", error);
  }
}

/**
 * 8. DOM Message Appenders
 */
function appendUserMessage(text) {
  const container = document.getElementById("messagesContainer");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message user-message";
  msgDiv.innerHTML = `
    <div class="message-avatar">
      <i class="fa-solid fa-user"></i>
    </div>
    <div class="message-content">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
  const container = document.getElementById("messagesContainer");
  const id = "typing-" + Date.now();
  const typingDiv = document.createElement("div");
  typingDiv.id = id;
  typingDiv.className = "message assistant-message";
  typingDiv.innerHTML = `
    <div class="message-avatar">
      <i class="fa-solid fa-sparkles"></i>
    </div>
    <div class="message-content">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const elem = document.getElementById(id);
  if (elem) elem.remove();
}

function appendAssistantResponse(data) {
  const container = document.getElementById("messagesContainer");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message assistant-message";

  const parsedMarkdown = marked.parse(data.answer);

  let cardsHtml = "";
  if (data.recommended_cafes && data.recommended_cafes.length > 0) {
    cardsHtml = `<div class="cafe-card-grid">`;
    data.recommended_cafes.forEach(cafe => {
      const tagsHtml = (cafe.tags || []).slice(0, 3).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join("");
      const distBadge = cafe.distance_km !== null && cafe.distance_km !== undefined 
        ? `<span class="badge-distance"><i class="fa-solid fa-car"></i> ${cafe.distance_km} km</span>` 
        : '';
      const navUrl = cafe.navigation_url || cafe.google_maps_url;

      cardsHtml += `
        <div class="cafe-card" id="card-${cafe.id}">
          <div class="cafe-card-header">
            <span class="cafe-card-title">${escapeHtml(cafe.name)}</span>
            <div class="cafe-card-badges">
              ${distBadge}
              <span class="badge-rating">⭐ ${cafe.rating}</span>
              <span class="badge-price">₹${cafe.price_for_two} for 2</span>
            </div>
          </div>
          <p style="font-size: 0.8rem; color: #94a3b8;"><i class="fa-solid fa-location-dot"></i> ${escapeHtml(cafe.area)}</p>
          <div class="cafe-card-tags">${tagsHtml}</div>
          <p style="font-size: 0.82rem; margin-bottom: 8px;">${escapeHtml(cafe.highlights)}</p>
          <div class="cafe-card-actions">
            <button class="btn-action btn-route" onclick="drawDrivingRoute(${cafe.lat}, ${cafe.lng}, '${cafe.id}')" title="Draw live driving route on map">
              <i class="fa-solid fa-route"></i> Route
            </button>
            <button class="btn-action btn-zoom" onclick="flyToCafe('${cafe.id}', ${cafe.lat}, ${cafe.lng})" title="Center map on cafe">
              <i class="fa-solid fa-location-crosshairs"></i> Zoom
            </button>
            <a href="${navUrl}" target="_blank" rel="noopener noreferrer" class="btn-action btn-gmaps" title="Open turn-by-turn driving directions in Google Maps">
              <i class="fa-solid fa-diamond-turn-right"></i> Navigate
            </a>
          </div>
        </div>
      `;
    });
    cardsHtml += `</div>`;
  }

  msgDiv.innerHTML = `
    <div class="message-avatar">
      <i class="fa-solid fa-sparkles"></i>
    </div>
    <div class="message-content">
      <div class="markdown-body">${parsedMarkdown}</div>
      ${cardsHtml}
    </div>
  `;

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function appendErrorMessage(text) {
  const container = document.getElementById("messagesContainer");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message assistant-message";
  msgDiv.innerHTML = `
    <div class="message-avatar" style="background: #ef4444;">
      <i class="fa-solid fa-triangle-exclamation"></i>
    </div>
    <div class="message-content" style="border-color: #ef4444;">
      <p style="color: #f87171;">${escapeHtml(text)}</p>
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

/**
 * 9. Interactive Map Actions
 */
window.flyToCafe = function(cafeId, lat, lng) {
  if (window.innerWidth <= 850) {
    switchMobileTab('map');
  }

  if (map) map.invalidateSize();
  map.flyTo([lat, lng], 16, {
    animate: true,
    duration: 1.2
  });

  const marker = allMarkers[cafeId];
  if (marker) {
    setTimeout(() => {
      marker.openPopup();
    }, 1200);
  }
};

window.drawDrivingRoute = drawDrivingRoute;

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}
