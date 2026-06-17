import sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import networkx as nx
import numpy as np
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import FOAF, DCTERMS

ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

LRE = Namespace("http://lre.epita.fr/kg/")

TEAM_COLORS = {
    "AA":      "#4363D8",
    "TIRF":    "#3CB44B",
    "IA":      "#E6194B",
    "SÉCUSYS": "#F58231",
    "MNSHS":   "#911EB4",
}
DEFAULT_COLOR = "#888888"


def load_graph() -> Graph:
    ttl = ROOT / "output" / "lre_kg.ttl"
    if not ttl.exists():
        sys.exit(f"Graph not found: {ttl}\nRun python step4/build_graph.py first.")
    g = Graph()
    g.parse(str(ttl))
    print(f"Graph loaded: {len(g)} triples")
    return g


def _team_label(uri: str) -> str:
    return uri.split("team_")[-1] if "team_" in uri else uri.split("/")[-1]


def _year_label(uri: str) -> str:
    return uri.split("year_")[-1] if "year_" in uri else uri.split("/")[-1]


def pubs_per_year(g: Graph) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    seen: set = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        if pub in seen:
            continue
        seen.add(pub)
        for y in g.objects(pub, LRE.inYear):
            counts[_year_label(str(y))] += 1
    return dict(sorted(counts.items()))


def plot_pubs_per_year(data: dict[str, int]) -> None:
    years = [y for y in data if y.isdigit() and 1980 <= int(y) <= 2025]
    years.sort()
    counts = [data[y] for y in years]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(years, counts, color="#4363D8", alpha=0.85)
    ax.set_title("Publications per year (LRE researchers)", fontsize=14)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of publications")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "pubs_per_year.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'pubs_per_year.png'}")


def pubs_per_team(g: Graph) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    seen_pairs: set = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        for r in g.objects(pub, LRE.authoredBy):
            for t in g.objects(r, LRE.memberOf):
                pair = (str(pub), str(t))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    counts[_team_label(str(t))] += 1
    return counts


def plot_pubs_per_team(data: dict[str, int]) -> None:
    teams = sorted(data, key=lambda k: -data[k])
    counts = [data[t] for t in teams]
    colors = [TEAM_COLORS.get(t, DEFAULT_COLOR) for t in teams]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(teams, counts, color=colors)
    ax.set_title("Publications per team (LRE)", fontsize=14)
    ax.set_xlabel("Number of publications")
    fig.tight_layout()
    fig.savefig(OUT / "pubs_per_team.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'pubs_per_team.png'}")


def top_researchers(g: Graph, n: int = 15) -> list[tuple[str, str, int]]:
    counts: dict[tuple, int] = defaultdict(int)
    lre_members: set = set()
    for r in g.subjects(LRE.memberOf, None):
        lre_members.add(r)

    for pub in g.subjects(RDF.type, LRE.Publication):
        for r in g.objects(pub, LRE.authoredBy):
            if r in lre_members:
                name = str(g.value(r, FOAF.name) or r)
                team = _team_label(str(g.value(r, LRE.memberOf) or ""))
                counts[(name, team)] += 1

    ranked = sorted(counts.items(), key=lambda x: -x[1])[:n]
    return [(k[0], k[1], v) for k, v in ranked]


def plot_top_researchers(data: list[tuple[str, str, int]]) -> None:
    names = [f"{d[0]} ({d[1]})" for d in data][::-1]
    counts = [d[2] for d in data][::-1]
    colors = [TEAM_COLORS.get(d[1], DEFAULT_COLOR) for d in data][::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(names, counts, color=colors)
    ax.set_title("Top 15 LRE researchers by publication count", fontsize=13)
    ax.set_xlabel("Number of publications")
    fig.tight_layout()
    fig.savefig(OUT / "top_researchers.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'top_researchers.png'}")


def build_coauthor_network(g: Graph) -> nx.Graph:
    lre_members: dict = {}
    for r in g.subjects(LRE.memberOf, None):
        name = str(g.value(r, FOAF.name) or r)
        team = _team_label(str(g.value(r, LRE.memberOf) or ""))
        lre_members[r] = (name, team)

    G = nx.Graph()
    for r, (name, team) in lre_members.items():
        G.add_node(str(r), label=name, team=team)

    for r in lre_members:
        for co in g.objects(r, LRE.coAuthorOf):
            if co in lre_members:
                G.add_edge(str(r), str(co))
    return G


def plot_coauthor_network(G: nx.Graph) -> None:
    if G.number_of_nodes() == 0:
        return
    pos = nx.spring_layout(G, seed=42, k=2.5)
    node_colors = [TEAM_COLORS.get(G.nodes[n].get("team", ""), DEFAULT_COLOR) for n in G.nodes]
    degrees = dict(G.degree())
    node_sizes = [200 + degrees[n] * 80 for n in G.nodes]

    fig, ax = plt.subplots(figsize=(12, 10))
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.35, edge_color="#cccccc")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_labels(G, pos, labels={n: G.nodes[n]["label"] for n in G.nodes},
                            ax=ax, font_size=7, font_weight="bold")

    legend_elements = [plt.Line2D([0], [0], marker="o", color="w",
                                  markerfacecolor=c, markersize=10, label=t)
                       for t, c in TEAM_COLORS.items()]
    ax.legend(handles=legend_elements, loc="upper left", title="Team")
    ax.set_title("LRE co-authorship network (node size = degree)", fontsize=14)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "coauthor_network.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'coauthor_network.png'}")


def team_collab_matrix(g: Graph) -> tuple[list[str], np.ndarray]:
    teams = sorted(TEAM_COLORS)
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    mat = np.zeros((n, n), dtype=int)

    seen_pubs: set = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        if pub in seen_pubs:
            continue
        seen_pubs.add(pub)
        pub_teams = []
        for r in g.objects(pub, LRE.authoredBy):
            for t in g.objects(r, LRE.memberOf):
                tl = _team_label(str(t))
                if tl in team_to_idx:
                    pub_teams.append(team_to_idx[tl])
        pub_teams = list(set(pub_teams))
        for i in pub_teams:
            for j in pub_teams:
                mat[i][j] += 1
    return teams, mat


def plot_team_heatmap(teams: list[str], mat: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(len(teams)))
    ax.set_yticks(range(len(teams)))
    ax.set_xticklabels(teams, rotation=45, ha="right")
    ax.set_yticklabels(teams)
    for i in range(len(teams)):
        for j in range(len(teams)):
            ax.text(j, i, str(mat[i, j]), ha="center", va="center", fontsize=10,
                    color="white" if mat[i, j] > mat.max() * 0.6 else "black")
    ax.set_title("Team collaboration matrix\n(cell = shared publications)", fontsize=13)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "team_heatmap.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'team_heatmap.png'}")


def topics_by_team(g: Graph) -> dict[str, dict[str, int]]:
    data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for pub in g.subjects(RDF.type, LRE.Publication):
        topic_node = g.value(pub, LRE.hasTopic)
        if topic_node is None:
            continue
        topic = str(g.value(topic_node, DCTERMS.title) or "Unknown")
        for r in g.objects(pub, LRE.authoredBy):
            for t in g.objects(r, LRE.memberOf):
                tl = _team_label(str(t))
                data[tl][topic] += 1
    return {k: dict(v) for k, v in data.items()}


def plot_topics_by_team(data: dict[str, dict[str, int]]) -> None:
    if not data:
        return
    all_topics = sorted({t for v in data.values() for t in v})
    teams = sorted(data)
    x = np.arange(len(teams))
    width = 0.8 / max(len(all_topics), 1)
    colors = cm.tab20(np.linspace(0, 1, len(all_topics)))

    fig, ax = plt.subplots(figsize=(14, 6))
    for i, topic in enumerate(all_topics):
        counts = [data.get(t, {}).get(topic, 0) for t in teams]
        offset = (i - len(all_topics) / 2) * width
        ax.bar(x + offset, counts, width=width * 0.9, label=topic, color=colors[i])

    ax.set_xticks(x)
    ax.set_xticklabels(teams)
    ax.set_title("Research topics per team", fontsize=13)
    ax.set_ylabel("Publications")
    ax.legend(loc="upper right", fontsize=6, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "topics_by_team.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'topics_by_team.png'}")


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


def collab_growth(g: Graph) -> None:
    lre_members: set = set(g.subjects(LRE.memberOf, None))

    year_internal: dict[str, set] = defaultdict(set)
    year_external: dict[str, set] = defaultdict(set)

    for pub in g.subjects(RDF.type, LRE.Publication):
        year_node = g.value(pub, LRE.inYear)
        if year_node is None:
            continue
        yr = _year_label(str(year_node))
        if not yr.isdigit():
            continue
        authors = list(g.objects(pub, LRE.authoredBy))
        lre_authors = [a for a in authors if a in lre_members]
        ext_authors = [a for a in authors if a not in lre_members]
        for la in lre_authors:
            for lb in lre_authors:
                if str(la) < str(lb):
                    year_internal[yr].add((str(la), str(lb)))
            for ea in ext_authors:
                year_external[yr].add((str(la), str(ea)))

    years = sorted(y for y in set(year_internal) | set(year_external)
                   if y.isdigit() and 1990 <= int(y) <= 2025)
    if not years:
        return

    int_counts = [len(year_internal.get(y, set())) for y in years]
    ext_counts = [len(year_external.get(y, set())) for y in years]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(years, int_counts, "o-", color="#4363D8", label="Within-LRE pairs", linewidth=2)
    ax.plot(years, ext_counts, "s--", color="#E6194B", label="LRE-external pairs", linewidth=2)
    ax.set_title("Collaboration pairs per year", fontsize=14)
    ax.set_xlabel("Year")
    ax.set_ylabel("New co-authorship pairs")
    ax.legend()
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "collab_growth.png", dpi=150)
    plt.close(fig)
    print(f"  → {OUT / 'collab_growth.png'}")


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
    teams, mat = team_collab_matrix(g)
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
