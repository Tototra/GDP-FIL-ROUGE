from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import networkx as nx
import numpy as np
from rdflib import Graph, Namespace, RDF

from trends_data import LRE, _team_label, _year_label

TEAM_COLORS = {
    "AA":      "#4363D8",
    "TIRF":    "#3CB44B",
    "IA":      "#E6194B",
    "SÉCUSYS": "#F58231",
    "MNSHS":   "#911EB4",
}
DEFAULT_COLOR = "#888888"

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)


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

def collab_growth(g: Graph) -> None:
    lre_members: set = set(g.subjects(LRE.memberOf, None))

    year_internal: dict[str, set] = {}
    year_external: dict[str, set] = {}

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
        year_internal.setdefault(yr, set())
        year_external.setdefault(yr, set())
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
