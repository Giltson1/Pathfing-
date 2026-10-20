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
// Public tile layers that do not require a provider API key.
const osmAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
const openStreetMap = L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { attribution: osmAttribution, maxZoom: 19 }
).addTo(map);

const hot = L.tileLayer(
    'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
    { attribution: `${osmAttribution} | Tiles &copy; HOT`, subdomains: 'abc', maxZoom: 19 }
);

const openTopoMap = L.tileLayer(
    'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    { attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)', subdomains: 'abc', maxZoom: 17 }
);


// Built-in Leaflet layer control
L.control.layers({
    'OpenStreetMap': openStreetMap,
    'Humanitarian': hot,
    'Topographic': openTopoMap
}).addTo(map);

let routeLayer = null;
let explorationLayer = null;
let explorationNodesLayer = null;
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
        // Typed text invalidates any coordinates chosen from an earlier suggestion.
        selectedCoords[coordKey] = null;
        // Wait until typing pauses before sending another autocomplete request.
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
                // Wrap around so keyboard navigation can cycle through results.
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
function makeLiveAnimator(layer, nodeLayer, color, perFrame) {
    // The server streams edges while the browser draws them over successive frames.
    const queue = [];
    let head = 0, finished = false, resolveFn;
    const done = new Promise((resolve) => (resolveFn = resolve));

    function step() {
        const backlog = queue.length - head;
        // Increase the per-frame batch with the backlog to drain large queues quickly.
        const edgesThisFrame = Math.max(perFrame, Math.ceil(backlog / 90));
        for (let k = 0; k < edgesThisFrame && head < queue.length; k++) {
            const [from, to] = queue[head++];
            L.polyline([from, to], { color, weight: 3, opacity: 0.25, dashArray: "4 6" }).addTo(layer);
            L.circleMarker(to, { radius: 3, color, fillOpacity: 0.9, opacity: 0.9 }).addTo(nodeLayer);
        }
        // Keep scheduling while work may still arrive or queued edges remain.
        if (head < queue.length || !finished) requestAnimationFrame(step);
        else resolveFn();
    }
    requestAnimationFrame(step);

    return {
        push: (segs) => queue.push(...segs),
        finish: () => (finished = true),
        done,
    };
}

function setLoading(on){
    const btn = document.getElementById("runBtn");
    btn.classList.toggle("loading", on);
    btn.disabled = on;
    btn.querySelector(".btn-text").textContent = on ? "Working..." : "▶ FIND PATH";
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

    // On small screens, switch to map-only view once a valid request starts.
    if (window.innerWidth <= 768) {
        document.body.classList.add("mobile-map-only");
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
        // fresh layers BEFORE the request so drawing starts immediately
        if (explorationLayer) map.removeLayer(explorationLayer);
        if (explorationNodesLayer) map.removeLayer(explorationNodesLayer);
        if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
        explorationLayer = L.layerGroup().addTo(map);
        explorationNodesLayer = L.layerGroup().addTo(map);

        const color = getAlgoColor(selectedAlgo);
        const edgesPerFrame = 1;
        const anim = makeLiveAnimator(explorationLayer, explorationNodesLayer, color, edgesPerFrame);

        let res = null;
        try {
            const response = await fetch("/route", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ start: startCoords, end: endCoords, algo: selectedAlgo }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Failed to fetch route");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buf = "";
            let hasStartedExploring = false;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                // Network chunks can end mid-message, so keep the last partial
                // line in buf and parse it after the next chunk arrives.
                buf += decoder.decode(value, { stream: true });
                const lines = buf.split("\n");
                buf = lines.pop();
                for (const line of lines) {
                    if (!line) continue;
                    const msg = JSON.parse(line);
                    if (msg.type === "status") {
                        document.querySelector("#runBtn .btn-text").textContent = msg.msg;
                    } else if (msg.type === "edges") {
                        if (!hasStartedExploring) {
                            hasStartedExploring = true;
                            document.querySelector("#runBtn .btn-text").textContent = "Exploring...";
                        }
                        anim.push(msg.edges);
                    }
                    else if (msg.type === "result") res = msg;
                    else if (msg.type === "error") throw new Error(msg.error);
                }
            }
        } finally {
            // Stop accepting animation work and wait until queued edges are drawn,
            // including when fetch or stream processing throws.
            anim.finish();
            await anim.done;
        }

        if (!res) throw new Error("Invalid route returned by server");
        const computMS = (performance.now() - t0).toFixed(2);

        if (routeLayer) map.removeLayer(routeLayer);
        routeLayer = L.polyline(res.path, {
            color: "#000000",
            weight: 5,
            opacity: 0.9,
        }).addTo(map);

        document.getElementById("statNodes").textContent = res.nodes_visited || res.path.length;
        document.getElementById("statCompute").textContent = `${computMS} ms`;
        document.getElementById("statsSection").style.display = "block";

        // Successful run: restore the sidebar on mobile too, not just on error.
        if (window.innerWidth <= 768) {
            document.body.classList.remove("mobile-map-only");
        }

    }catch (error){
        console.error("Error during pathfinding:", error);
        showToast("Error: " + error.message, true);
    } finally {
        setLoading(false);
    }
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast show ${isError ? "error" : "success"}`;
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.className = "toast";
        if (window.innerWidth <= 768) {
            document.body.classList.remove("mobile-map-only");
        }
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