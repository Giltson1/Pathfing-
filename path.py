import heapq
from collections import deque

def dijkstra(graph, start, end):
    pq = [(0, start)]
    distance = {node: float('inf') for node in graph}
    distance[start] = 0
    prev_node = {node: None for node in graph}
    visited = set()
    order = []

    while pq:
        current_d, current_node = heapq.heappop(pq)

        if current_node in visited:
            continue
        visited.add(current_node)
        order.append((current_node, prev_node[current_node]))

        if current_node == end:
            break

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
    return distance[end], path[::-1], order

def bfs(graph, start, end):
    prev = {start: None}
    visited = {start}
    que = deque([start])
    order = []

    while que:
        node = que.popleft()
        order.append((node, prev[node]))
        if node == end:
            break
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                prev[neighbor] = node
                que.append(neighbor)

    if end not in prev:
        return [], order

    path = []
    cur = end 
    
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1], order


def dfs(graph, start, end, visited=None, parent=None, order=None):
    if visited is None:
        visited = set()
    if order is None:
        order = []
    visited.add(start)
    order.append((start, parent))
    if start == end:
        return [start], order

    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            subpath, order = dfs(graph, neighbor, end, visited, start, order)
            if subpath:
                return [start] + subpath, order

    return [], order

def a_star(graph, src, dst, h):
    g = {node: float('inf') for node in graph}
    g[src] = 0
    pq = [(h.get(src, 0), src)]
    prev = {node: None for node in graph}
    visited = set()
    order = []

    while pq:
        f, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        order.append((node, prev[node]))
        if node == dst:
            break
        for neighbor, weight in graph.get(node, {}).items():
            if neighbor in visited:
                continue
            new_g = g[node] + weight
            if new_g < g[neighbor]:
                g[neighbor] = new_g
                prev[neighbor] = node
                heapq.heappush(pq, (new_g + h.get(neighbor, 0), neighbor))

    if g[dst] == float('inf'):
        return float('inf'), [], order

    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return g[dst], path[::-1], order

def greedy_best_first(graph, start, end, h):
    pq = [(h.get(start, 0), start)]
    prev = {node: None for node in graph}
    visited = set()
    order = []

    while pq:
        _, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        order.append((node, prev[node]))
        if node == end:
            break
        for neighbor in graph.get(node, {}):
            if neighbor not in visited:
                if prev[neighbor] is None:
                    prev[neighbor] = node
                heapq.heappush(pq, (h.get(neighbor, 0), neighbor))

    if prev[end] is None and start != end:
        return [], order

    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1], order