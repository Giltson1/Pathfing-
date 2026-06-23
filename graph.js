
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