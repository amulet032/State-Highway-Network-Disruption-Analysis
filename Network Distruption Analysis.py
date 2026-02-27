"""
transport_disruption_chch.py

Road Network Disruption Impact Analysis (Open Data) - Christchurch, NZ

Pipeline:
1) Download OSM drive network for Christchurch (cached to data/*.graphml)
2) Sample random OD pairs from network nodes
3) Compute baseline shortest path distances (by length)
4) Simulate single-edge disruptions (remove one edge at a time)
5) Output ranking CSV + bar chart + map of top critical edges

Requirements:
- osmnx
- networkx
- geopandas
- pandas
- numpy
- matplotlib

Usage examples:
  python transport_disruption_chch.py --place "Christchurch, New Zealand" --download
  python transport_disruption_chch.py --place "Christchurch, New Zealand" --run_all
  python transport_disruption_chch.py --run_all --n_od 400 --n_edges 25 --top_n 8

Notes:
- This uses distance-based impacts (edge length). You can extend to travel time by adding speeds.
- OD sampling is random; set --seed for reproducibility.
"""

from __future__ import annotations

import argparse
import copy
import os
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import networkx as nx
import osmnx as ox


# -----------------------------
# Utilities
# -----------------------------

@dataclass
class Paths:
    data_dir: str = "data"
    out_dir: str = "outputs"

    @property
    def graphml_path(self) -> str:
        return os.path.join(self.data_dir, "christchurch_drive.graphml")

    @property
    def od_path(self) -> str:
        return os.path.join(self.data_dir, "od_pairs.csv")

    @property
    def ranking_path(self) -> str:
        return os.path.join(self.out_dir, "impact_ranking.csv")

    @property
    def bar_path(self) -> str:
        return os.path.join(self.out_dir, "impact_bar.png")

    @property
    def map_path(self) -> str:
        return os.path.join(self.out_dir, "map_critical_edges.png")


def ensure_dirs(paths: Paths) -> None:
    os.makedirs(paths.data_dir, exist_ok=True)
    os.makedirs(paths.out_dir, exist_ok=True)


def safe_int(x: Any) -> int:
    # GraphML sometimes loads node IDs as strings; OSMnx generally uses ints.
    try:
        return int(x)
    except Exception:
        return x


def shortest_path_length_m(G: nx.MultiDiGraph, o: Any, d: Any, weight: str = "length") -> Optional[float]:
    try:
        return float(nx.shortest_path_length(G, o, d, weight=weight))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def pick_random_edges(G: nx.MultiDiGraph, n: int, seed: int = 42) -> List[Tuple[Any, Any, Any, Dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    edges = list(G.edges(keys=True, data=True))
    if not edges:
        return []
    idx = rng.choice(len(edges), size=min(n, len(edges)), replace=False)
    return [edges[i] for i in idx]


def canonical_edge_id(u: Any, v: Any, k: Any) -> str:
    return f"{u}-{v}-{k}"


# -----------------------------
# Steps
# -----------------------------

def download_network(place: str, paths: Paths, force: bool = False) -> nx.MultiDiGraph:
    """
    Download OSM drive network for a place and cache as GraphML.
    """
    ensure_dirs(paths)

    if os.path.exists(paths.graphml_path) and not force:
        print(f"[download] Using cached graph: {paths.graphml_path}")
        return ox.load_graphml(paths.graphml_path)

    print(f"[download] Downloading drive network for: {place}")
    G = ox.graph_from_place(place, network_type="drive")

    # Ensure lengths exist (OSMnx usually includes length, but safe to recompute)
    G = ox.add_edge_lengths(G)

    ox.save_graphml(G, paths.graphml_path)
    print(f"[download] Saved graph to: {paths.graphml_path}")
    return G


def sample_od_pairs(G: nx.MultiDiGraph, n_od: int, seed: int) -> pd.DataFrame:
    """
    Sample random origin-destination node pairs from the graph.
    """
    random.seed(seed)
    nodes = list(G.nodes)
    if len(nodes) < 2:
        raise ValueError("Graph has fewer than 2 nodes; cannot sample OD pairs.")

    pairs = []
    for _ in range(n_od):
        o, d = random.sample(nodes, 2)
        pairs.append((o, d))

    return pd.DataFrame(pairs, columns=["origin", "dest"])


def compute_baseline(G: nx.MultiDiGraph, od_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute baseline shortest path distance for each OD pair.
    """
    rows = []
    unreachable = 0
    for _, r in od_df.iterrows():
        o = safe_int(r["origin"])
        d = safe_int(r["dest"])
        dist = shortest_path_length_m(G, o, d, weight="length")
        if dist is None:
            unreachable += 1
        rows.append({"origin": o, "dest": d, "baseline_dist_m": dist})

    out = pd.DataFrame(rows)
    frac_unreachable = unreachable / len(out) if len(out) else np.nan
    print(f"[baseline] Computed baseline distances. Unreachable fraction: {frac_unreachable:.3f}")
    return out


def disruption_simulation(
    G: nx.MultiDiGraph,
    baseline_df: pd.DataFrame,
    test_edges: List[Tuple[Any, Any, Any, Dict[str, Any]]],
) -> pd.DataFrame:
    """
    Remove one edge at a time and measure impact on reachable baseline OD pairs.
    Impact metrics:
      - mean_dist_increase_m (mean(new - baseline) over ODs still reachable)
      - frac_unreachable (among ODs that were reachable in baseline)
    """
    # Filter to baseline-reachable ODs only (so we measure new disconnection due to disruption)
    base_reach = baseline_df.dropna(subset=["baseline_dist_m"]).copy()
    n_base = len(base_reach)
    if n_base == 0:
        raise ValueError("All OD pairs are unreachable in baseline. Try increasing n_od or check graph.")

    results = []
    for (u, v, k, data) in test_edges:
        G2 = copy.deepcopy(G)
        if not G2.has_edge(u, v, k):
            continue

        G2.remove_edge(u, v, k)

        deltas = []
        unreachable = 0

        for _, r in base_reach.iterrows():
            o = safe_int(r["origin"])
            d = safe_int(r["dest"])
            base = float(r["baseline_dist_m"])

            new = shortest_path_length_m(G2, o, d, weight="length")
            if new is None:
                unreachable += 1
            else:
                deltas.append(new - base)

        mean_increase = float(np.mean(deltas)) if deltas else np.nan
        frac_unreachable = unreachable / n_base if n_base else np.nan

        # Road name can be list or str or missing
        name = data.get("name", None)
        if isinstance(name, list) and len(name) > 0:
            name = name[0]

        results.append(
            {
                "edge_id": canonical_edge_id(u, v, k),
                "u": u,
                "v": v,
                "key": k,
                "road_name": name,
                "mean_dist_increase_m": mean_increase,
                "frac_unreachable": frac_unreachable,
                "n_od_baseline_reachable": int(n_base),
            }
        )

    df = pd.DataFrame(results)

    # Sort: prioritize disconnections, then mean distance increase
    if not df.empty:
        df = df.sort_values(["frac_unreachable", "mean_dist_increase_m"], ascending=[False, False])

    print(f"[simulate] Simulated {len(df)} edge disruptions (from {len(test_edges)} sampled).")
    return df


def plot_bar(df_rank: pd.DataFrame, out_path: str, top_n: int) -> None:
    """
    Bar chart for top N by mean distance increase (or sorted order).
    """
    if df_rank.empty:
        print("[plot] Ranking is empty; skipping bar chart.")
        return

    df_top = df_rank.head(top_n).copy()
    labels = []
    for _, r in df_top.iterrows():
        nm = r.get("road_name")
        if pd.isna(nm) or nm is None:
            nm = f"edge {r['edge_id']}"
        labels.append(str(nm))

    plt.figure(figsize=(10, 6))
    plt.bar(range(len(df_top)), df_top["mean_dist_increase_m"])
    plt.xticks(range(len(df_top)), labels, rotation=45, ha="right")
    plt.ylabel("Mean Distance Increase (m)")
    plt.title(f"Top {top_n} Critical Road Segments (Distance Impact)")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[plot] Saved bar chart: {out_path}")


def plot_map_highlight_edges(
    G: nx.MultiDiGraph, df_rank: pd.DataFrame, out_path: str, top_n: int
) -> None:
    """
    Plot base network + highlight top N edges.
    (Note: simple straight-line highlighting between node coords; fast and robust.)
    """
    if df_rank.empty:
        print("[plot] Ranking is empty; skipping map.")
        return

    df_top = df_rank.head(top_n).copy()

    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color="lightgray",
        edge_linewidth=0.6,
        show=False,
        close=False,
    )

    # Highlight top edges
    for _, r in df_top.iterrows():
        u = safe_int(r["u"])
        v = safe_int(r["v"])
        k = safe_int(r["key"])

        if not G.has_edge(u, v, k):
            continue

        # Use node coordinates
        try:
            xs = [G.nodes[u]["x"], G.nodes[v]["x"]]
            ys = [G.nodes[u]["y"], G.nodes[v]["y"]]
            ax.plot(xs, ys, linewidth=3)
        except Exception:
            continue

    ax.set_title(f"Most Critical Road Segments (Top {top_n}) - Simulated Disruption")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[plot] Saved map: {out_path}")


# -----------------------------
# Main
# -----------------------------

def run_all(args: argparse.Namespace) -> None:
    paths = Paths(args.data_dir, args.out_dir)
    ensure_dirs(paths)

    # Step 1: download/load graph
    G = download_network(args.place, paths, force=args.force_download)

    # Step 2: OD pairs (load or generate)
    if os.path.exists(paths.od_path) and not args.force_od:
        print(f"[od] Using cached OD pairs: {paths.od_path}")
        od_df = pd.read_csv(paths.od_path)
    else:
        print(f"[od] Sampling {args.n_od} OD pairs (seed={args.seed})")
        od_df = sample_od_pairs(G, args.n_od, args.seed)
        od_df.to_csv(paths.od_path, index=False)
        print(f"[od] Saved OD pairs: {paths.od_path}")

    # Step 3: baseline distances
    baseline_df = compute_baseline(G, od_df)

    # Step 4: sample edges to test
    test_edges = pick_random_edges(G, args.n_edges, seed=args.seed)
    if not test_edges:
        raise RuntimeError("No edges found to test.")

    # Step 5: simulate disruptions
    rank_df = disruption_simulation(G, baseline_df, test_edges)
    rank_df.to_csv(paths.ranking_path, index=False)
    print(f"[out] Saved ranking CSV: {paths.ranking_path}")

    # Step 6: plots
    plot_bar(rank_df, paths.bar_path, args.top_n)
    plot_map_highlight_edges(G, rank_df, paths.map_path, args.top_n)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Christchurch road network disruption impact analysis (open data).")
    p.add_argument("--place", type=str, default="Christchurch, New Zealand", help="OSM place query.")
    p.add_argument("--data_dir", type=str, default="data", help="Data directory.")
    p.add_argument("--out_dir", type=str, default="outputs", help="Outputs directory.")

    p.add_argument("--n_od", type=int, default=300, help="Number of random OD pairs.")
    p.add_argument("--n_edges", type=int, default=15, help="Number of random edges to test for disruption.")
    p.add_argument("--top_n", type=int, default=5, help="Top N edges to visualize.")
    p.add_argument("--seed", type=int, default=42, help="Random seed.")

    p.add_argument("--download", action="store_true", help="Download/cache the network only (no analysis).")
    p.add_argument("--run_all", action="store_true", help="Run the full pipeline.")
    p.add_argument("--force_download", action="store_true", help="Force re-download of the network.")
    p.add_argument("--force_od", action="store_true", help="Force re-sampling of OD pairs.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    paths = Paths(args.data_dir, args.out_dir)
    ensure_dirs(paths)

    if args.download:
        _ = download_network(args.place, paths, force=args.force_download)
        return

    if args.run_all or (not args.download and not args.run_all):
        # Default behavior: run all if no flags were provided
        run_all(args)


if __name__ == "__main__":
    main()