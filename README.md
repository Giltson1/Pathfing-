# PathFindr

PathFindr shows how several popular pathfinding algorithms perform on a map.

Enter a start and destination address, choose an algorithm, and watch it search a real road network in real time.

## Algorithms

PathFindr supports the following algorithms:

- Dijkstra's algorithm
- A* search
- Breadth-first search (BFS)
- Depth-first search (DFS)
- Greedy best-first search

## Local setup

Clone the repository:

```bash
git clone https://github.com/Giltson1/pathfinging.git
cd pathfinging
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project folder and add your Geoapify API key. The key is used for address autocomplete and geocoding. You can get a key at [Geoapify](https://www.geoapify.com/):

```env
API_KEY=your_key_here
```

## Run

Start the application on the default port, 5000:

```bash
python app.py
```

To use a different port, pass it as an argument:

```bash
python app.py 8080
```

## How it works

- Geoapify converts the entered addresses into coordinates.
- The application downloads road data from the OpenStreetMap map API. Requests are limited to small areas.
- The Flask backend builds a graph from the road data and streams each visited node to the browser.
- The frontend uses Leaflet to draw the search progress and the resulting route.
  
## Testing

As of now I've only tested routes within a 10 mile radius. Anything past that may be slow, since a bigger area means more roads to download and more nodes to draw.

## Work in progress 
-Mobile version
-Stop button when you quick run
