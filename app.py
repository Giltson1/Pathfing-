import math
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from dotenv import load_dotenv

from path import dijkstra, bfs, dfs, a_star, greedy_best_first

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__)

ROAD_REQUEST_TIMEOUT = (5, 20)
GRAPH_CACHE_TTL = 1800
_graph_cache = {}
ROAD_REQUEST_HEADERS = {
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


def fetch_osm_map(south, west, north, east):
    map_url = "https://api.openstreetmap.org/api/0.6/map"
    if north - south > 0.25 or east - west > 0.25:
        raise requests.RequestException(
            "OpenStreetMap map API only supports bounding boxes up to 0.25 degrees"
        )

    try:
        resp = requests.get(
            map_url,
            params={"bbox": f"{west},{south},{east},{north}"},
            headers=ROAD_REQUEST_HEADERS,
            timeout=ROAD_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        elements = [
            {
                "type": "node",
                "id": int(node.attrib["id"]),
                "lat": float(node.attrib["lat"]),
                "lon": float(node.attrib["lon"]),
            }
            for node in root.findall("node")
        ]
        for way in root.findall("way"):
            if any(tag.attrib.get("k") == "highway" for tag in way.findall("tag")):
                elements.append({
                    "type": "way",
                    "id": int(way.attrib["id"]),
                    "nodes": [int(node.attrib["ref"]) for node in way.findall("nd")],
                })
        if any(element["type"] == "way" for element in elements):
            return {"elements": elements}
        raise requests.RequestException(
            f"{map_url}: no roads found for bbox ({south},{west},{north},{east})"
        )
    except requests.RequestException:
        raise
    except (ET.ParseError, KeyError, ValueError) as e:
        raise requests.RequestException(f"{map_url}: {e}") from e


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


def get_graph(south, west, north, east):
    # Snap outward to a 0.01-degree grid so nearby routes share a download.
    south = math.floor(south * 100) / 100
    west = math.floor(west * 100) / 100
    north = math.ceil(north * 100) / 100
    east = math.ceil(east * 100) / 100
    key = (south, west, north, east)

    cached = _graph_cache.get(key)
    if cached and time.time() - cached[0] < GRAPH_CACHE_TTL:
        return cached[1]

    graph, coords = build_graph(fetch_osm_map(south, west, north, east))
    if graph:
        _graph_cache[key] = (time.time(), (graph, coords))
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
            graph, coords = get_graph(south, west, north, east)
        except requests.RequestException as e:
            yield emit({"type": "error", "error": f"Failed to fetch road network: {e}"})
            return

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

        visited_count, result = 0, None
        while True:
            try:
                node, parent = next(gen)
            except StopIteration as e:
                result = e.value
                break
            visited_count += 1
            if parent is not None:
                edge = [list(coords[parent]), list(coords[node])]
                yield emit({"type": "edges", "edges": [edge]})

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
            "nodes_visited": visited_count,
        })

    return Response(stream_with_context(stream()), mimetype="application/x-ndjson")


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000 
    
    app.run(host="0.0.0.0", port=port)