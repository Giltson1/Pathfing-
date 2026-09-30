import math
import json
import os
from pathlib import Path
import requests
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from dotenv import load_dotenv

from path import dijkstra, bfs, dfs, a_star, greedy_best_first

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__)

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
OVERPASS_HEADERS = {
    "User-Agent": "PathFindr/1.0 (local pathfinding application)",
}
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
    query = (
        f'[out:json][timeout:20];'
        f'way["highway"]({south},{west},{north},{east});'
        "out body;>;out skel qt;"
    )
    errors = []
    for url in OVERPASS_URLS:
        try:
            resp = requests.get(
                url,
                params={"data": query},
                headers=OVERPASS_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("elements"):
                return data
            errors.append(f"{url}: empty road graph for bbox ({south},{west},{north},{east})")
        except requests.RequestException as e:
            errors.append(f"{url}: {e}")
        except ValueError as e:
            errors.append(f"{url}: invalid JSON response: {e}")
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

    def emit(obj):
        return json.dumps(obj) + "\n"

    def stream():
        margin = 0.005
        south = min(start_lat, end_lat) - margin
        north = max(start_lat, end_lat) + margin
        west = min(start_lon, end_lon) - margin
        east = max(start_lon, end_lon) + margin

        yield emit({"type": "status", "msg": "Fetching roads..."})
        try:
            osm_data = fetch_road_network(south, west, north, east)
        except requests.RequestException as e:
            yield emit({"type": "error", "error": f"Failed to fetch road network: {e}"})
            return

        graph, coords = build_graph(osm_data)
        if not graph:
            yield emit({"type": "error", "error": "No road network found in this area"})
            return

        start_node = nearest_node(graph, coords, start_lat, start_lon)
        end_node = nearest_node(graph, coords, end_lat, end_lon)

        h = None
        if algo in ("astar", "greedy"):
            h = {n: haversine(coords[n][0], coords[n][1], end_lat, end_lon) for n in graph}

        if algo == "dijkstra":
            gen = dijkstra(graph, start_node, end_node)
        elif algo == "bfs":
            gen = bfs(graph, start_node, end_node)
        elif algo == "dfs":
            gen = dfs(graph, start_node, end_node)
        elif algo == "astar":
            gen = a_star(graph, start_node, end_node, h)
        elif algo == "greedy":
            gen = greedy_best_first(graph, start_node, end_node, h)
        else:
            yield emit({"type": "error", "error": f"Unknown algorithm '{algo}'"})
            return

        batch, visited_count, result = [], 0, None
        while True:
            try:
                node, parent = next(gen)
            except StopIteration as e:
                result = e.value
                break
            visited_count += 1
            if parent is not None:
                batch.append([list(coords[parent]), list(coords[node])])
            if len(batch) >= 25:
                yield emit({"type": "edges", "edges": batch})
                batch = []
        if batch:
            yield emit({"type": "edges", "edges": batch})

        if algo in ("dijkstra", "astar"):
            distance, node_path = result
        else:
            node_path = result
            distance = path_length(graph, node_path)

        if not node_path or distance in (float("inf"), None):
            yield emit({"type": "error", "error": "No path found between these points"})
            return

        yield emit({
            "type": "result",
            "path": [list(coords[n]) for n in node_path],
            "distance": round(distance, 2),
            "duration": round(distance / 15000.0 * 3600.0, 2),
            "nodes_visited": visited_count,
        })

    return Response(stream_with_context(stream()), mimetype="application/x-ndjson")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)