import sys
from pathlib import Path

import networkx as nx
from rdflib import Graph

from trends_data import (
    pubs_per_year, pubs_per_team, top_researchers,
    build_coauthor_network, team_collab_matrix, topics_by_team,
)
from trends_plot import (
    TEAM_COLORS, OUT,
    plot_pubs_per_year, plot_pubs_per_team, plot_top_researchers,
    plot_coauthor_network, plot_team_heatmap,
    collab_growth,
)

ROOT = Path(__file__).parent.parent


def load_graph() -> Graph:
    ttl = ROOT / "output" / "lre_kg.ttl"
    if not ttl.exists():
        sys.exit(f"Graph not found: {ttl}\nRun python step4/build_graph.py first.")
    g = Graph()
    g.parse(str(ttl))
    print(f"Graph loaded: {len(g)} triples")
    return g


def network_summary(G: nx.Graph) -> None:
    if G.number_of_nodes() == 0:
        print("  (no nodes in co-authorship network)")
        return
    print(f"\n  Co-authorship network (LRE members only)")
    print(f"    Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    comps = list(nx.connected_components(G))
    print(f"    Connected components: {len(comps)}")
    largest = max(comps, key=len)
    print(f"    Largest component: {len(largest)} nodes")

    if G.number_of_edges() > 0:
        betw = nx.betweenness_centrality(G)
        top5 = sorted(betw.items(), key=lambda x: -x[1])[:5]
        print("    Top 5 by betweenness centrality:")
        for node, score in top5:
            print(f"      {G.nodes[node].get('label', node)}: {score:.3f}")

        try:
            communities = nx.algorithms.community.louvain_communities(G, seed=42)
            print(f"    Louvain communities detected: {len(communities)}")
        except Exception:
            pass

        density = nx.density(G)
        print(f"    Network density: {density:.3f}")


def main() -> None:
    print("Loading graph …")
    g = load_graph()

    print("\n[1] Publications per year")
    py = pubs_per_year(g)
    plot_pubs_per_year(py)
    recent = {k: v for k, v in py.items() if k.isdigit() and int(k) >= 2015}
    if recent:
        peak = max(recent, key=lambda k: recent[k])
        print(f"    Peak recent year: {peak} ({recent[peak]} pubs)")

    print("\n[2] Publications per team")
    pt = pubs_per_team(g)
    plot_pubs_per_team(pt)
    for t, c in sorted(pt.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")

    print("\n[3] Top researchers")
    top = top_researchers(g)
    plot_top_researchers(top)
    for name, team, cnt in top[:5]:
        print(f"    {name} ({team}): {cnt} pubs")

    print("\n[4] Co-authorship network")
    G = build_coauthor_network(g)
    plot_coauthor_network(G)
    network_summary(G)

    print("\n[5] Team collaboration heatmap")
    teams = sorted(TEAM_COLORS)
    mat = team_collab_matrix(g, teams)
    plot_team_heatmap(teams, mat)

    print("\n[6] Topics by team")
    tbt = topics_by_team(g)
    if tbt:
        plot_topics_by_team(tbt)
        for team, topics in sorted(tbt.items()):
            top3 = sorted(topics.items(), key=lambda x: -x[1])[:3]
            print(f"    {team}: " + ", ".join(f"{t} ({c})" for t, c in top3))
    else:
        print("    No hasTopic triples found — rebuild the graph first.")

    print("\n[7] Collaboration growth over time")
    collab_growth(g)

    print(f"\nAll figures saved to {OUT}/")


if __name__ == "__main__":
    main()
