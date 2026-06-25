import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)

@app.route("/api/config")
def config():
    return jsonify({"geoapify_key": os.getenv("API_KEY", "")})

if __name__ == "__main__":
    app.run(debug=True)