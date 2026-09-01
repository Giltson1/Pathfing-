import math
import os
from pathlib import Path
import requests
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from path import dijkstra, bfs, dfs, a_star, greedy_best_first

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__)

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
OVERPASS_HEADERS = {
    "User-Agent": "PathFindr/1.0 (+https://example.com)",
    "Accept": "application/json",
}
GEOAPIFY_ROUTING_URL = "https://api.geoapify.com/v1/routing"

# Only these filenames are servable from BASE_DIR. Anything else (including
# .env and the .py source files) is refused.
ALLOWED_STATIC = {"graph.js", "style.css"}


@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    if filename not in ALLOWED_STATIC:
        return "Not found", 404
    return send_from_directory(str(BASE_DIR), filename)


@app.route("/api/config")
def config():
    api_key = os.getenv("API_KEY") or os.getenv("MY_API_KEY") or ""
    return jsonify({"geoapify_key": api_key})


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_road_network(south, west, north, east):
    queries = [
        f"""
        [out:json][timeout:25];
        (
            way["highway"!~"footway|path|steps|cycleway|pedestrian|track"]
                ({south},{west},{north},{east});
        );
        out body;
        >;
        out skel qt;
        """,
        f"""
        [out:json][timeout:25];
        (
            way["highway"]
                ({south},{west},{north},{east});
        );
        out body;
        >;
        out skel qt;
        """,
    ]
    errors = []
    for query in queries:
        for url in OVERPASS_URLS:
            try:
                resp = requests.post(url, data={"data": query}, headers=OVERPASS_HEADERS, timeout=30)
                if resp.status_code == 406:
                    errors.append(f"{url}: 406 Not Acceptable")
                    continue
                resp.raise_for_status()
                data = resp.json()
                if data.get("elements"):
                    return data
                errors.append(f"{url}: empty road graph for bbox ({south},{west},{north},{east})")
            except requests.RequestException as e:
                errors.append(f"{url}: {e}")
                continue
            except ValueError as e:
                errors.append(f"{url}: invalid JSON response: {e}")
                continue
    raise requests.RequestException("All Overpass mirrors failed or returned no roads:\n" + "\n".join(errors))


def build_graph(osm_data):
    coords = {}
    for el in osm_data.get("elements", []):
        if el["type"] == "node":
            coords[el["id"]] = (el["lat"], el["lon"])

    graph = {}
    for el in osm_data.get("elements", []):
        if el["type"] == "way":
            node_ids = el.get("nodes", [])
            for i in range(len(node_ids) - 1):
                a, b = node_ids[i], node_ids[i + 1]
                if a not in coords or b not in coords:
                    continue
                dist = haversine(*coords[a], *coords[b])
                graph.setdefault(a, {})[b] = dist
                graph.setdefault(b, {})[a] = dist

    return graph, coords


def fetch_geoapify_route(start_lat, start_lon, end_lat, end_lon):
    api_key = os.getenv("API_KEY") or os.getenv("MY_API_KEY") or ""
    if not api_key:
        raise ValueError("Geoapify API key is missing")

    params = {
        "waypoints": f"{start_lat},{start_lon}|{end_lat},{end_lon}",
        "mode": "drive",
        "apiKey": api_key,
    }

    resp = requests.get(GEOAPIFY_ROUTING_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    features = payload.get("features") or []
    if not features:
        raise ValueError("Geoapify routing returned no features")

    geometry = features[0].get("geometry", {})
    coords = geometry.get("coordinates") or []
    if not coords:
        raise ValueError("Geoapify routing returned no geometry")

    if geometry.get("type") == "MultiLineString":
        flattened = []
        for segment in coords:
            for point in segment:
                if len(point) >= 2:
                    flattened.append([point[1], point[0]])
        path_coords = flattened
    else:
        path_coords = []
        for point in coords:
            if len(point) >= 2:
                path_coords.append([point[1], point[0]])

    if not path_coords:
        raise ValueError("Geoapify routing returned malformed geometry")

    props = features[0].get("properties", {})
    distance = float(props.get("distance", 0.0) or 0.0)
    duration = float(props.get("time", 0.0) or 0.0)
    return path_coords, distance, duration


def nearest_node(graph, coords, lat, lon):
    return min(graph.keys(), key=lambda n: haversine(lat, lon, *coords[n]))


def path_length(graph, node_path):
    if not node_path or len(node_path) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(node_path, node_path[1:]):
        total += graph.get(a, {}).get(b, 0.0)
    return total


@app.route("/route", methods=["POST"])
def route():
    data = request.get_json(silent=True) or {}
    start = data.get("start")
    end = data.get("end")
    algo = (data.get("algo") or "dijkstra").lower()

    if not start or not end:
        return jsonify(error="Missing start or end coordinates"), 400

    try:
        start_lat = float(start["lat"])
        start_lon = float(start["lon"])
        end_lat = float(end["lat"])
        end_lon = float(end["lon"])
    except (TypeError, ValueError, KeyError):
        return jsonify(error="Invalid start or end coordinates"), 400

    force_local = bool(data.get("force_local", False))
    api_key = os.getenv("API_KEY") or os.getenv("MY_API_KEY") or ""
    # If an API key is available and user did not force local computation, try Geoapify first
    if api_key and not force_local:
        try:
            path_coords, distance, duration = fetch_geoapify_route(start_lat, start_lon, end_lat, end_lon)
            return jsonify({
                "path": path_coords,
                "distance": round(distance, 2),
                "duration": round(duration, 2),
                "nodes_visited": len(path_coords),
                "exploration": [],
            })
        except (requests.RequestException, ValueError):
            pass

    margin = 0.02
    south = min(start_lat, end_lat) - margin
    north = max(start_lat, end_lat) + margin
    west = min(start_lon, end_lon) - margin
    east = max(start_lon, end_lon) + margin

    try:
        osm_data = fetch_road_network(south, west, north, east)
    except requests.RequestException as e:
        return jsonify(error=f"Failed to fetch road network: {e}"), 502

    graph, coords = build_graph(osm_data)
    if not graph:
        return jsonify(error="No road network found in this area"), 404

    start_node = nearest_node(graph, coords, start_lat, start_lon)
    end_node = nearest_node(graph, coords, end_lat, end_lon)

    if algo == "dijkstra":
        distance, node_path, order = dijkstra(graph, start_node, end_node)
    elif algo == "bfs":
        node_path, order = bfs(graph, start_node, end_node)
        distance = path_length(graph, node_path)
    elif algo == "dfs":
        node_path, order = dfs(graph, start_node, end_node)
        distance = path_length(graph, node_path)
    elif algo == "astar":
        h = {n: haversine(*coords[n], end_lat, end_lon) for n in graph}
        distance, node_path, order = a_star(graph, start_node, end_node, h)
    elif algo == "greedy":
        h = {n: haversine(*coords[n], end_lat, end_lon) for n in graph}
        node_path, order = greedy_best_first(graph, start_node, end_node, h)
        distance = path_length(graph, node_path)
    else:
        return jsonify(error=f"Unknown algorithm '{algo}'"), 400

    if not node_path or distance in (float("inf"), None):
        return jsonify(error="No path found between these points"), 404

    path_coords = [list(coords[n]) for n in node_path]
    duration = distance / 15000.0 * 3600.0  # assumes 15 km/h avg speed

    exploration = [
        [list(coords[parent]), list(coords[node])]
        for node, parent in order
        if parent is not None and parent in coords and node in coords
    ]

    return jsonify({
        "path": path_coords,
        "distance": round(distance, 2),
        "duration": round(duration, 2),
        "nodes_visited": len(node_path),
        "exploration": exploration,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 