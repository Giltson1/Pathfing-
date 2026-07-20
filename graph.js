

let API_KEY = null;

async function init() {
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        API_KEY = data.geoapify_key?.trim() || null;

        if (!API_KEY) {
            console.error("Geoapify API key is missing. Address autocomplete will be disabled.");
            return;
        }

        attachAutocomplete("startInput", "start");
        attachAutocomplete("endInput", "end");
    } catch (error) {
        console.error("Failed to initialize address autocomplete", error);
    }
}

init();
// selecting which algorithm to run 
function selectAlgo(el) {
    document.querySelectorAll(".algo-btn").forEach((b) => b.classList.remove("active"));
    el.classList.add("active");
    selectedAlgo = el.dataset.algo;
}

//MAP diplaye 
const map = L.map("map").setView([40.758, -73.9855], 13);
// default map layer 
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "©OpenStreetMap ©CartoDB",
    maxZoom: 19,
}).addTo(map);

// switch betwen map layer 
const voyager = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
  {
    attribution: '"©OpenStreetMap ©CartoDB',
    subdomains: 'abcd',
    maxZoom: 20
  }
);

const positron = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  {
    attribution: '"©OpenStreetMap ©CartoDB',
    subdomains: 'abcd',
    maxZoom: 20
  }
);

const darkMatter = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  {
    attribution: '"©OpenStreetMap ©CartoDB',
    subdomains: 'abcd',
    maxZoom: 20
  }
);


// Built-in Leaflet layer control
L.control.layers({
  'Voyager': voyager,
  'Positron': positron,
  'Dark Matter': darkMatter
}).addTo(map);

let routeLayer = null;
let startMarker = null;
let endMarker = null;
let selectedAlgo = "dijkstra";

const debounceTimers = {}; // Store debounce timers for each input field
const selectedCoords = { start: null, end: null }; // Store selected coordinates for start and end inputs
const autocompleteDropdowns = new Set();
let autocompleteClickHandlerAdded = false;
let toastTimeout = null;

function attachAutocomplete(inputId, coordKey) {
    const input = document.getElementById(inputId);

    const dropdown = document.createElement("ul");
    dropdown.className = "autocomplete-dropdown";
    dropdown.id = `${inputId}-dropdown`;
    input.parentElement.appendChild(dropdown);
    autocompleteDropdowns.add(dropdown);

    if (!autocompleteClickHandlerAdded) {
        document.addEventListener("click", (e) => {
            autocompleteDropdowns.forEach((menu) => {
                if (!menu.contains(e.target) && !document.getElementById(menu.id.replace("-dropdown", ""))?.contains(e.target)) {
                    menu.innerHTML = "";
                    menu.style.display = "none";
                }
            });
        });
        autocompleteClickHandlerAdded = true;
    }

    input.addEventListener("input", () => {
        selectedCoords[coordKey] = null;
        clearTimeout(debounceTimers[inputId]);
        debounceTimers[inputId] = setTimeout(() => fetchSuggestions(input, dropdown, coordKey), 300);
    });

    input.addEventListener("keydown", (e) => {
        const items = dropdown.querySelectorAll("li");
        const active = dropdown.querySelector("li.highlighted");

        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (!active) {
                items[0]?.classList.add("highlighted");
            } else {
                const next = active.nextElementSibling;
                active.classList.remove("highlighted");
                (next || items[0]).classList.add("highlighted");
            }
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (active) {
                const prev = active.previousElementSibling;
                active.classList.remove("highlighted");
                (prev || items[items.length - 1]).classList.add("highlighted");
            }
        } else if (e.key === "Enter") {
            if (active) {
                e.preventDefault();
                active.click();
            } else {
                runPathfinding();
            }
        } else if (e.key === "Escape") {
            dropdown.innerHTML = "";
            dropdown.style.display = "none";
        }
    });
}

async function fetchSuggestions(input, dropdown, coordKey) {
    const query = input.value.trim();
    if (query.length < 3 || !API_KEY) {
        dropdown.innerHTML = "";
        dropdown.style.display = "none";
        return;
    }

    const url = `https://api.geoapify.com/v1/geocode/autocomplete?text=${encodeURIComponent(query)}&limit=5&format=json&apiKey=${API_KEY}`;
    try {
        const res = await fetch(url);
        const data = await res.json();
        renderDropdown(input, dropdown, coordKey, data.results || []);
    } catch {
        dropdown.innerHTML = "";
        dropdown.style.display = "none";
    }
}

function renderDropdown(input, dropdown, coordKey, results) {
    dropdown.innerHTML = "";

    if (results.length === 0) {
        dropdown.style.display = "none";
        return;
    }

    results.forEach((r) => {
        const li = document.createElement("li");
        // Bold the first part (name/street), dimmer for the rest
        const parts = r.formatted.split(",");
        const main = parts[0].trim();
        const sub = parts.slice(1).join(",").trim();
        li.innerHTML = `<span class="ac-main">${main}</span>${sub ? `<span class="ac-sub">, ${sub}</span>` : ""}`;

        li.addEventListener("click", () => {
            input.value = r.formatted;
            // Save coords so we skip a redundant geocode call
            selectedCoords[coordKey] = { lat: r.lat, lon: r.lon };
            dropdown.innerHTML = "";
            dropdown.style.display = "none";
        });

        dropdown.appendChild(li);
    });

    dropdown.style.display = "block";
}

// Geocode an address to coordinates using Geoapify to wait for the user 
// to select an address from the autocomplete suggestions. 
// If the user has already selected a suggestion, 
// we can skip this step and use the saved coordinates.

async function geocodeAddress(address) {
    const url = `https://api.geoapify.com/v1/geocode/search?text=${encodeURIComponent(address)}&format=json&apiKey=${API_KEY}`;
    try {
        const res = await fetch(url);
        const data = await res.json();
        if (!data.results || data.results.length === 0) {
            throw new Error("No geocoding results returned");
        }
        return data.results[0];
    } catch (error) {
        throw new Error(error.message || "Failed to geocode address");
    }
}

// Reverse geocode coordinates to an address using Geoapify.
async function reverseGeocode(lat, lon) {
    const url = `https://api.geoapify.com/v1/geocode/reverse?lat=${lat}&lon=${lon}&format=json&apiKey=${API_KEY}`;
    try {
        const res = await fetch(url);
        const data = await res.json();
        return data.results[0];
    } catch {
        throw new Error("Failed to reverse geocode coordinates");
    }
}
function setLoading(on){
    const btn = document.getElementById("runBtn");
    btn.classList.toggle("loading", on);
    btn.disabled = on;
}

// Function to run the pathfinding algorithm
async function runPathfinding(){

    // Get the start and end addresses from the input fields
    const startaddress = document.getElementById("startInput").value.trim();
    const endaddress = document.getElementById("endInput").value.trim();

    if (!startaddress || !endaddress){
        showToast("Please enter both start and end addresses.", true);
        return;
    }
    setLoading(true);

    // Geocode the addresses to get coordinates
    try{ 
        const[startCoords, endCoords] = await Promise.all([
            selectedCoords.start ? Promise.resolve(selectedCoords.start) : geocodeAddress(startaddress),
            selectedCoords.end ? Promise.resolve(selectedCoords.end) : geocodeAddress(endaddress),
        ]);

        if (startMarker) map.removeLayer(startMarker);
        if (endMarker) map.removeLayer(endMarker);

        startMarker = L.marker([startCoords.lat, startCoords.lon]).addTo(map)
            .bindPopup("Start: " + startaddress);
        endMarker = L.marker([endCoords.lat, endCoords.lon]).addTo(map)
            .bindPopup("End: " + endaddress);

        map.fitBounds([
            [startCoords.lat, startCoords.lon],
            [endCoords.lat, endCoords.lon],
        ]);
         
        const t0 = performance.now();
        const response = await fetch("/route", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ start: startCoords, end: endCoords, algo: selectedAlgo }),
        });
       
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || "Failed to fetch route");
        }
        const res = await response.json();
        const computMS = (performance.now() - t0).toFixed(2);

        if (!res.path || !Array.isArray(res.path) || res.path.length === 0) {
            throw new Error("Invalid route returned by server");
        }

        if (routeLayer) map.removeLayer(routeLayer);
        routeLayer = L.polyline(res.path, {
            color: getAlgoColor(selectedAlgo),
            weight: 5,
            opacity: 0.7,
        }).addTo(map);

        document.getElementById("statDist").textContent = formatDistance(res.distance);
        document.getElementById("statTime").textContent = formatDuration(res.duration);
        document.getElementById("statNodes").textContent = res.nodes_visited || res.path.length;
        document.getElementById("statCompute").textContent = `${computMS} ms`;
        document.getElementById("statsSection").style.display = "block";

    }catch (error){
        console.error("Error during pathfinding:", error);
        showToast("Error: " + error.message, true);
    } finally {
        setLoading(false);
    }
}
function formatDistance(meters) {
    if (typeof meters !== "number" || Number.isNaN(meters)) {
        return "—";
    }
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(2)} km`;
    }
    return `${Math.round(meters)} m`;
}

function formatDuration(seconds) {
    if (typeof seconds !== "number" || Number.isNaN(seconds)) {
        return "—";
    }
    if (seconds >= 3600) {
        return `${(seconds / 3600).toFixed(1)} h`;
    }
    if (seconds >= 60) {
        return `${Math.round(seconds / 60)} min`;
    }
    return `${Math.round(seconds)} s`;
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast show ${isError ? "error" : "success"}`;
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.className = "toast";
    }, 3500);
}

function getAlgoColor(algo) {
    return {
        dijkstra: "#00e5ff",
        astar: "#7c4dff",
        bfs: "#69f0ae",
        dfs: "#ff6d00",
        greedy: "#ff4081",
    }[algo] || "#ffffff";
}



