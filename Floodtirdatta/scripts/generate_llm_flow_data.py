import json
import os
import csv
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GRAPH_JS = os.path.join(HERE, "graph_data.js")

# Output files
PATHS_TXT = os.path.join(ROOT, "data", "llm", "canal_flow_paths.txt")
EDGES_CSV = os.path.join(ROOT, "data", "llm", "canal_flow_edges.csv")
ADJACENCY_JSON = os.path.join(ROOT, "data", "llm", "canal_flow_adjacency.json")
NODES_CSV = os.path.join(ROOT, "data", "llm", "canal_nodes_metadata.csv")

def main():
    # Ensure data/llm directory exists
    os.makedirs(os.path.join(ROOT, "data", "llm"), exist_ok=True)
    
    if not os.path.exists(GRAPH_JS):
        print(f"Error: {GRAPH_JS} not found")
        return
        
    with open(GRAPH_JS, "r", encoding="utf-8") as f:
        content = f.read()
        
    start = content.find("{")
    end = content.rfind("}") + 1
    graph = json.loads(content[start:end])
    
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    
    node_by_id = {n["id"]: n for n in nodes}
    
    # 1. Build adjacency list and calculate out-degree
    adj_out = {}
    for e in edges:
        s = e["s"]
        t = e["t"]
        adj_out.setdefault(s, []).append(t)
        
    # Major receptors (Rivers and other known major river channels)
    major_receptors = {"แม่น้ำเจ้าพระยา", "แม่น้ำท่าจีน", "แม่น้ำบางปะกง"}
    
    # 2. BFS to find the shortest path from each node to its terminal sink(s)
    # A node is terminal if:
    # - It has out-degree = 0 (no outgoing edges)
    # - Or it is a major receptor (river)
    def find_shortest_paths(start_node):
        if start_node in major_receptors or start_node not in adj_out or len(adj_out[start_node]) == 0:
            return [[start_node]]
            
        queue = deque([(start_node, [start_node])])
        visited = {start_node}
        terminal_paths = []
        
        # We perform BFS to find shortest path to any sink or major receptor
        # In BFS, the first path that reaches a sink/river will be the shortest.
        # To handle multiple sinks/rivers at the same shortest length, we gather all of them at that level.
        found_level = None
        
        while queue:
            curr, path = queue.popleft()
            
            if found_level is not None and len(path) > found_level:
                break
                
            # If current node is a sink or major receptor, save this path
            is_sink = curr in major_receptors or curr not in adj_out or len(adj_out[curr]) == 0
            if is_sink:
                terminal_paths.append(path)
                found_level = len(path)
                continue
                
            for neighbor in adj_out.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
                    
        # If BFS finished and we didn't find any path (e.g. cycle with no exit), return the path we traversed
        if not terminal_paths:
            return [path]
            
        return terminal_paths

    # Generate paths for all nodes
    all_paths = []
    for n in nodes:
        node_id = n["id"]
        paths = find_shortest_paths(node_id)
        for path in paths:
            all_paths.append(path)
            
    # 3. Save to canal_flow_paths.txt
    print(f"Writing paths to {PATHS_TXT}...")
    with open(PATHS_TXT, "w", encoding="utf-8") as f:
        f.write("# Bangkok Canal Flow Paths (KlongMap)\n")
        f.write("# Format: Source Canal -> ... -> River/Sink\n\n")
        for path in sorted(all_paths, key=lambda x: (len(x), x[0])):
            f.write(" -> ".join(path) + "\n")
            
    # 4. Save to canal_flow_edges.csv
    print(f"Writing edges to {EDGES_CSV}...")
    with open(EDGES_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target"])
        for e in sorted(edges, key=lambda x: (x["s"], x["t"])):
            writer.writerow([e["s"], e["t"]])
            
    # 5. Save to canal_flow_adjacency.json
    print(f"Writing adjacency list to {ADJACENCY_JSON}...")
    with open(ADJACENCY_JSON, "w", encoding="utf-8") as f:
        json.dump(adj_out, f, ensure_ascii=False, indent=2)
        
    # 6. Save to canal_nodes_metadata.csv
    print(f"Writing nodes metadata to {NODES_CSV}...")
    with open(NODES_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "district", "lon", "lat", "level"])
        for n in sorted(nodes, key=lambda x: x["id"]):
            pt = n.get("pt", [None, None])
            # Handle points
            lon = pt[0] if len(pt) > 0 else ""
            lat = pt[1] if len(pt) > 1 else ""
            writer.writerow([
                n["id"],
                n.get("type", ""),
                n.get("district", ""),
                lon,
                lat,
                n.get("level", -1)
            ])
            
    print("All LLM flow data files generated successfully!")

if __name__ == "__main__":
    main()
