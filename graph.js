
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

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "©OpenStreetMap ©CartoDB",
    maxZoom: 19,
}).addTo(map);

let routeLayer = null;
let startMarker = null;
let endMarker = null;
let selectedAlgo = "dijkstra";

// auto complete the address input fields

const debounceTimers = {} // Store debounce timers for each input field
const selectedCoords = { start: null, end: null }; // Store selected coordinates for start and end inputs

function attachAutocomplete(inputId, coordKey) {
    const input = document.getElementById(inputId);

    // Create dropdown element
    const dropdown = document.createElement("ul");
    dropdown.className = "autocomplete-dropdown";
    dropdown.id = `${inputId}-dropdown`;
    input.parentElement.appendChild(dropdown);

    input.addEventListener("input", () => {
        // Clear saved coords — user is typing something new
        selectedCoords[coordKey] = null;

        clearTimeout(debounceTimers[inputId]);
        debounceTimers[inputId] = setTimeout(() => fetchSuggestions(input, dropdown, coordKey), 300);
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.innerHTML = "";
            dropdown.style.display = "none";
        }
    });

    // Keyboard nav inside dropdown
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
                e.preventDefault(); // don't also trigger runPathfinding via Enter
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
    try{
        const res = await fetch(url);
        const data = await res.json();
        return data.results[0];
    } catch {
        throw new Error("Failed to geocode address");
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
    setLoading(true);
}

