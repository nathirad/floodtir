import json
import heapq
import math
import os
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH_JS = os.path.join(HERE, "graph_data.js")

def main():
    print("Loading graph_data.js...")
    with open(GRAPH_JS, "r", encoding="utf-8") as f:
        content = f.read()

    start = content.find("{")
    end = content.rfind("}") + 1
    prefix = content[:start]
    suffix = content[end:]
    
    graph = json.loads(content[start:end])
    nodes = graph["nodes"]
    edges = graph["edges"]
    
    node_by_id = {n["id"]: n for n in nodes}
    node_ids = set(node_by_id.keys())
    
    print(f"Loaded {len(nodes)} nodes and {len(edges)} edges.")
    
    # Define major sinks
    major_sinks = {"แม่น้ำเจ้าพระยา", "แม่น้ำท่าจีน", "แม่น้ำบางปะกง", "อ่าวไทย"}
    for nid in node_ids:
        if "สุดเขต" in nid or "สุดระยะ" in nid or "สิ้นสุดระยะ" in nid:
            major_sinks.add(nid)
            
    def get_pt(nid):
        n = node_by_id[nid]
        pt = n.get("pt", [0, 0])
        return pt[0], pt[1]

    def distance(nid1, nid2):
        x1, y1 = get_pt(nid1)
        x2, y2 = get_pt(nid2)
        return math.hypot(x1 - x2, y1 - y2)

    # Build undirected adjacency list
    adj_undir = {}
    for e in edges:
        s = e["s"]
        t = e["t"]
        if s in node_ids and t in node_ids:
            w = distance(s, t)
            adj_undir.setdefault(s, []).append((t, w))
            adj_undir.setdefault(t, []).append((s, w))

    # Find connected components in the undirected graph
    visited_comp = set()
    components = []
    for nid in node_ids:
        if nid not in visited_comp:
            comp = []
            queue = deque([nid])
            visited_comp.add(nid)
            while queue:
                curr = queue.popleft()
                comp.append(curr)
                for neighbor, w in adj_undir.get(curr, []):
                    if neighbor not in visited_comp:
                        visited_comp.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    print(f"Detected {len(components)} connected components in undirected graph.")

    # Get coordinates of all major sinks
    major_sink_pts = []
    for sink in major_sinks:
        if sink in node_ids:
            major_sink_pts.append(get_pt(sink))

    # Default if no sinks found (unlikely, but fallback)
    if not major_sink_pts:
        major_sink_pts = [(100.5, 13.75)]

    def min_dist_to_any_major_sink(nid):
        x, y = get_pt(nid)
        return min(math.hypot(x - sx, y - sy) for sx, sy in major_sink_pts)

    # Compute Dijkstra potentials from designated sinks in each component
    dist = {}
    pq = []

    for comp in components:
        comp_set = set(comp)
        comp_sinks = comp_set & major_sinks
        
        if comp_sinks:
            # Component contains actual major sink(s)
            for sink in comp_sinks:
                dist[sink] = 0.0
                heapq.heappush(pq, (0.0, sink))
        else:
            # Choose node closest geographically to any major sink as local sink
            local_sink = min(comp, key=min_dist_to_any_major_sink)
            dist[local_sink] = 0.0
            heapq.heappush(pq, (0.0, local_sink))

    print("Running Dijkstra algorithm to calculate node potentials...")
    while pq:
        d, curr = heapq.heappop(pq)
        if d > dist[curr]:
            continue
        for neighbor, w in adj_undir.get(curr, []):
            new_d = d + w
            if neighbor not in dist or new_d < dist[neighbor]:
                dist[neighbor] = new_d
                heapq.heappush(pq, (new_d, neighbor))

    # Re-orient edges based on potentials
    new_edges = []
    reversed_count = 0
    tie_count = 0
    
    for e in edges:
        s = e["s"]
        t = e["t"]
        if s not in node_ids or t not in node_ids:
            continue
        
        ds = dist.get(s, float('inf'))
        dt = dist.get(t, float('inf'))
        
        if ds > dt:
            new_edges.append({"s": s, "t": t})
        elif ds < dt:
            new_edges.append({"s": t, "t": s})
            reversed_count += 1
        else:
            # Tie break (lexicographical sorting of ID to avoid cycles on ties)
            if s > t:
                new_edges.append({"s": s, "t": t})
            else:
                new_edges.append({"s": t, "t": s})
            tie_count += 1

    print(f"Edge adjustment complete: reversed {reversed_count} edges, resolved {tie_count} ties.")

    # Verification Step: Check for remaining cycles
    new_adj_out = {}
    for e in new_edges:
        new_adj_out.setdefault(e["s"], []).append(e["t"])
        
    visited_cycle = {} # 0=unvisited, 1=visiting, 2=visited
    cycle_count = 0
    cycles = []
    
    def check_cycle(node, path):
        nonlocal cycle_count
        visited_cycle[node] = 1
        for neighbor in new_adj_out.get(node, []):
            state = visited_cycle.get(neighbor, 0)
            if state == 1:
                cycle_count += 1
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif state == 0:
                check_cycle(neighbor, path + [neighbor])
        visited_cycle[node] = 2
        
    for nid in node_ids:
        if visited_cycle.get(nid, 0) == 0:
            check_cycle(nid, [nid])
            
    print(f"Verification: remaining cycles = {cycle_count}")
    if cycle_count > 0:
        print("ERROR: Cycles detected in the new graph layout!")
        for c in cycles[:5]:
            print("  Cycle:", " -> ".join(c))
        return

    # Update the level of each node to represent its hop distance to nearest sink
    # Set levels for nodes that are reachable to major sinks
    # Run BFS backwards from major sinks to label level layer
    adj_in = {}
    for e in new_edges:
        adj_in.setdefault(e["t"], []).append(e["s"])
        
    bfs_queue = deque()
    levels = {}
    for nid in node_ids:
        if nid in major_sinks:
            levels[nid] = 0
            bfs_queue.append(nid)
            
    while bfs_queue:
        curr = bfs_queue.popleft()
        curr_lvl = levels[curr]
        for prev in adj_in.get(curr, []):
            if prev not in levels:
                levels[prev] = curr_lvl + 1
                bfs_queue.append(prev)
                
    # Update nodes array
    for n in nodes:
        nid = n["id"]
        n["level"] = levels.get(nid, -1) # -1 if in isolated components

    # Save graph back to graph_data.js
    graph["nodes"] = nodes
    graph["edges"] = new_edges

    # Re-generate adjacency map based on updated directed edges
    adjacency = {}
    for e in new_edges:
        adjacency.setdefault(e["s"], []).append(e["t"])
    graph["adjacency"] = adjacency
    
    print(f"Writing updated graph back to {GRAPH_JS}...")
    with open(GRAPH_JS, "w", encoding="utf-8") as f:
        f.write(prefix + json.dumps(graph, ensure_ascii=False) + suffix)
        
    print("Graph successfully healed and updated in graph_data.js!")

if __name__ == "__main__":
    main()
