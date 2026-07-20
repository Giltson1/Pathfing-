import heapq
from collections import deque

def dijkstra(graph, start, end):
    pq = [(0, start)]
    distance = {node: float('inf') for node in graph}
    distance[start] = 0
    prev_node = {node: None for node in graph}
    visited = set()

    while pq:
        current_d, current_node = heapq.heappop(pq)

        if current_node == end:
            break

        if current_node in visited:
            continue
        visited.add(current_node)

        for neighbor, weight in graph[current_node].items():
            if neighbor in visited:
                continue
            new_dist = current_d + weight
            if new_dist < distance[neighbor]:
                distance[neighbor] = new_dist
                prev_node[neighbor] = current_node
                heapq.heappush(pq, (new_dist, neighbor))

    path = []
    current = end
    while current is not None:
        path.append(current)
        current = prev_node[current]
    return distance[end], path[::-1]

def bfs(graph, start, end):
    prev = {start: None}
    visited = {start}
    que = deque([start])

    while que:
        node = que.popleft()
        if node == end:
            break
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                prev[neighbor] = node
                que.append(neighbor)

    if end not in prev:
        return []

    path = []
    cur = end 
    
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]


def dfs(graph, start, end, visited=None):
    if visited is None:
        visited = set()
    visited.add(start)
    if start == end:
        return [start]

    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            subpath = dfs(graph, neighbor, end, visited)
            if subpath:
                return [start] + subpath

    return []

def a_star(graph, src, dst, h):
    g = {node: float('inf') for node in graph}
    g[src] = 0
    pq = [(h.get(src, 0), src)]
    prev = {node: None for node in graph}
    visited = set()

    while pq:
        f, node = heapq.heappop(pq)
        if node == dst:
            break
        if node in visited:
            continue
        visited.add(node)
        for neighbor, weight in graph.get(node, {}).items():
            if neighbor in visited:
                continue
            new_g = g[node] + weight
            if new_g < g[neighbor]:
                g[neighbor] = new_g
                prev[neighbor] = node
                heapq.heappush(pq, (new_g + h.get(neighbor, 0), neighbor))

    if g[dst] == float('inf'):
        return float('inf'), []

    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return g[dst], path[::-1]

def greedy_best_first(graph, start, end, h):
    pq = [(h.get(start, 0), start)]
    prev = {node: None for node in graph}
    visited = set()

    while pq:
        _, node = heapq.heappop(pq)
        if node == end:
            break
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph.get(node, {}):
            if neighbor not in visited:
                if prev[neighbor] is None:
                    prev[neighbor] = node
                heapq.heappush(pq, (h.get(neighbor, 0), neighbor))

    if prev[end] is None and start != end:
        return []

    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]
