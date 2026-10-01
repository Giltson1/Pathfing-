import heapq
from collections import deque


def _reconstruct_path(prev, end):
    if end is None or end not in prev:
        return []

    path = []
    current = end
    while current is not None:
        path.append(current)
        current = prev[current]
    return path[::-1]


def dijkstra(graph, start, end):
    pq = [(0, start)]
    distance = {node: float('inf') for node in graph}
    distance[start] = 0
    prev_node = {node: None for node in graph}
    visited = set()

    while pq:
        current_d, current_node = heapq.heappop(pq)

        if current_node in visited:
            continue
        visited.add(current_node)
        yield current_node, prev_node[current_node]

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

    if distance.get(end, float('inf')) == float('inf'):
        return float('inf'), []

    return distance[end], _reconstruct_path(prev_node, end)

def bfs(graph, start, end):
    prev = {start: None}
    visited = {start}
    que = deque([start])

    while que:
        node = que.popleft()
        yield node, prev[node]
        if node == end:
            break
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                prev[neighbor] = node
                que.append(neighbor)

    if end not in prev:
        return []

    return _reconstruct_path(prev, end)


def dfs(graph, start, end):

    visited = {start}
    prev = {start: None}
    stack = [start]

    while stack:
        node = stack.pop()
        yield node, prev[node]
        if node == end:
            break
        for neighbor in reversed(list(graph.get(node, []))):
            if neighbor not in visited:
                visited.add(neighbor)
                prev[neighbor] = node
                stack.append(neighbor)

    if end not in prev:
        return []

    return _reconstruct_path(prev, end)

def a_star(graph, src, dst, h):
    g = {node: float('inf') for node in graph}
    g[src] = 0
    pq = [(h.get(src, 0), src)]
    prev = {node: None for node in graph}
    visited = set()

    while pq:
        f, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        yield node, prev[node]
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

    if g.get(dst, float('inf')) == float('inf'):
        return float('inf'), []

    return g[dst], _reconstruct_path(prev, dst)

def greedy_best_first(graph, start, end, h):
    pq = [(h.get(start, 0), start)]
    prev = {node: None for node in graph}
    visited = set()

    while pq:
        _, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        yield node, prev[node]
        if node == end:
            break
        for neighbor in graph.get(node, {}):
            if neighbor not in visited:
                if prev[neighbor] is None:
                    prev[neighbor] = node
                heapq.heappush(pq, (h.get(neighbor, 0), neighbor))

    if start != end and (end not in prev or prev[end] is None):
        return []

    return _reconstruct_path(prev, end)