import time
import math
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from path import dijkstra, bfs, dfs, a_star
 
app = Flask(__name__)
CORS(app)  # allow requests from index.html (localhost file or dev server)
 
OSRM_URL = "http://router.project-osrm.org"  # free public OSRM instance