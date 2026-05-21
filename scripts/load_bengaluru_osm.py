"""
ResQ — Bengaluru OSM Road Network Loader
=========================================
Downloads the drivable road network for Bengaluru via OSMnx
and saves it as a GraphML file for use by the spatial engine.

Output: app/data/raw/bengaluru_drive.graphml

Run from project root:
    python scripts/load_bengaluru_osm.py
"""

import os
import sys
import time

# ── Output path ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "app", "data", "raw")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GRAPH_PATH = os.path.join(OUTPUT_DIR, "bengaluru_drive.graphml")


def main():
    # Lazy import — osmnx pulls in heavy deps
    import osmnx as ox

    print("ResQ OSM Road Network Loader")
    print("=" * 50)

    # ── Download Bengaluru drivable network ──────────────────────────────
    # Bengaluru bounding box (generous to cover the full urban area)
    # North: Yelahanka (13.12), South: Electronic City (12.82)
    # West: Vijayanagar (77.48), East: Whitefield (77.78)
    NORTH, SOUTH = 13.12, 12.82
    EAST, WEST = 77.78, 77.48

    print(f"\nBounding box: N={NORTH} S={SOUTH} E={EAST} W={WEST}")
    print("Downloading drivable road network from OSM...")

    t0 = time.time()

    G = ox.graph_from_bbox(
        bbox=(NORTH, SOUTH, EAST, WEST),
        network_type="drive",
        retain_all=False,      # drop disconnected islands
        truncate_by_edge=True, # keep edges that cross the bbox boundary
    )

    elapsed = time.time() - t0
    print(f"Download complete in {elapsed:.1f}s")

    # ── Graph stats ──────────────────────────────────────────────────────
    nodes = len(G.nodes)
    edges = len(G.edges)
    print(f"\nGraph statistics:")
    print(f"  Nodes (intersections):  {nodes:,}")
    print(f"  Edges (road segments):  {edges:,}")

    # ── Save ─────────────────────────────────────────────────────────────
    print(f"\nSaving to {GRAPH_PATH}...")
    ox.save_graphml(G, filepath=GRAPH_PATH)

    size_mb = os.path.getsize(GRAPH_PATH) / (1024 * 1024)
    print(f"Saved: {size_mb:.1f} MB")

    # ── Summary report ───────────────────────────────────────────────────
    report = f"""ResQ OSM Network Report
========================
Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}
Region: Bengaluru (bbox: N={NORTH} S={SOUTH} E={EAST} W={WEST})
Network type: drive
Nodes: {nodes:,}
Edges: {edges:,}
File: bengaluru_drive.graphml ({size_mb:.1f} MB)
"""
    report_path = os.path.join(OUTPUT_DIR, "osm_report.txt")
    with open(report_path, "w") as f:
        f.write(report)

    print(report)
    print("Done.")


if __name__ == "__main__":
    main()
