import json
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


def load_graph():
    ttl = ROOT / "output" / "lre_kg.ttl"
    if not ttl.exists():
        sys.exit(f"Graph not found: {ttl}\nRun python step4/build_graph.py first.")
    g = Graph()
    g.parse(str(ttl))
    print(f"Graph loaded: {len(g)} triples")
    return g


def _team_label(uri):
    return uri.split("team_")[-1] if "team_" in uri else uri.split("/")[-1]


def _year_label(uri):
    return uri.split("year_")[-1] if "year_" in uri else uri.split("/")[-1]


def analyse_pubs_per_year(g):
    counts = defaultdict(int)
    seen = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        if pub in seen:
            continue
        seen.add(pub)
        for y in g.objects(pub, LRE.inYear):
            counts[_year_label(str(y))] += 1

    years = sorted(y for y in counts)
    values = [counts[y] for y in years]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(years, values, color="#4363D8", alpha=0.85)
    ax.set_title("Publications per year (LRE researchers)", fontsize=14)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of publications")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "pubs_per_year.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'pubs_per_year.png'}")

    recent = {y: counts[y] for y in years if int(y) >= 2015}
    if recent:
        peak = max(recent, key=recent.get)
        print(f"    Peak recent year: {peak} ({recent[peak]} pubs)")


def analyse_pubs_per_team(g):
    counts = defaultdict(int)
    seen_pairs = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        for r in g.objects(pub, LRE.authoredBy):
            for t in g.objects(r, LRE.memberOf):
                pair = (str(pub), str(t))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    counts[_team_label(str(t))] += 1

    teams = sorted(counts, key=lambda k: -counts[k])
    values = [counts[t] for t in teams]
    colors = [TEAM_COLORS.get(t, DEFAULT_COLOR) for t in teams]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(teams, values, color=colors)
    ax.set_title("Publications per team (LRE)", fontsize=14)
    ax.set_xlabel("Number of publications")
    fig.tight_layout()
    fig.savefig(OUT / "pubs_per_team.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'pubs_per_team.png'}")
    for t, c in zip(teams, values):
        print(f"    {t}: {c}")


def analyse_top_researchers(g, n = 15):
    lre_members = set(g.subjects(LRE.memberOf, None))
    counts = defaultdict(int)
    for pub in g.subjects(RDF.type, LRE.Publication):
        for r in g.objects(pub, LRE.authoredBy):
            if r in lre_members:
                name = str(g.value(r, FOAF.name) or r)
                team = _team_label(str(g.value(r, LRE.memberOf) or ""))
                counts[(name, team)] += 1

    ranked = sorted(counts.items(), key=lambda x: -x[1])[:n]
    data = [(k[0], k[1], v) for k, v in ranked]

    names = [f"{d[0]} ({d[1]})" for d in data][::-1]
    values = [d[2] for d in data][::-1]
    colors = [TEAM_COLORS.get(d[1], DEFAULT_COLOR) for d in data][::-1]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(names, values, color=colors)
    ax.set_title(f"Top {n} LRE researchers by publication count", fontsize=13)
    ax.set_xlabel("Number of publications")
    fig.tight_layout()
    fig.savefig(OUT / "top_researchers.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'top_researchers.png'}")
    for name, team, cnt in data[:5]:
        print(f"    {name} ({team}): {cnt} pubs")


def analyse_coauthor_network(g):
    lre_members = {}
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

    if G.number_of_nodes() == 0:
        print("  (no nodes in co-authorship network)")
        return G

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
    print(f"  -> {OUT / 'coauthor_network.png'}")

    comps = list(nx.connected_components(G))
    print(f"    Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    print(f"    Connected components: {len(comps)}, largest: {len(max(comps, key=len))} nodes")
    print(f"    Network density: {nx.density(G):.3f}")

    return G


def analyse_betweenness(G, n=10):
    if G.number_of_edges() == 0:
        return
    betw = nx.betweenness_centrality(G)
    ranked = sorted(betw.items(), key=lambda x: -x[1])[:n]
    labels = [G.nodes[node].get("label", node) for node, _ in ranked]
    scores = [score for _, score in ranked]
    colors = [TEAM_COLORS.get(G.nodes[node].get("team", ""), DEFAULT_COLOR) for node, _ in ranked]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels[::-1], scores[::-1], color=colors[::-1])
    ax.set_title(f"Top {n} researchers by betweenness centrality", fontsize=13)
    ax.set_xlabel("Betweenness centrality")
    fig.tight_layout()
    fig.savefig(OUT / "betweenness.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'betweenness.png'}")
    for node, score in ranked[:5]:
        print(f"    {G.nodes[node].get('label', node)} ({G.nodes[node].get('team', '?')}): {score:.3f}")


def analyse_team_heatmap(g):
    teams = sorted(TEAM_COLORS)
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    mat = np.zeros((n, n), dtype=int)

    seen = set()
    for pub in g.subjects(RDF.type, LRE.Publication):
        if pub in seen:
            continue
        seen.add(pub)
        pub_teams = list({team_to_idx[_team_label(str(t))]
                          for r in g.objects(pub, LRE.authoredBy)
                          for t in g.objects(r, LRE.memberOf)
                          if _team_label(str(t)) in team_to_idx})
        for i in pub_teams:
            for j in pub_teams:
                mat[i][j] += 1

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(teams, rotation=45, ha="right")
    ax.set_yticklabels(teams)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, str(mat[i, j]), ha="center", va="center", fontsize=10,
                    color="white" if mat[i, j] > mat.max() * 0.6 else "black")
    ax.set_title("Team collaboration matrix\n(cell = shared publications)", fontsize=13)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "team_heatmap.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'team_heatmap.png'}")


def analyse_topics_by_team(g):
    data = defaultdict(lambda: defaultdict(int))
    for pub in g.subjects(RDF.type, LRE.Publication):
        topic_node = g.value(pub, LRE.hasTopic)
        if topic_node is None:
            continue
        topic = str(g.value(topic_node, DCTERMS.title) or "Unknown")
        for r in g.objects(pub, LRE.authoredBy):
            for t in g.objects(r, LRE.memberOf):
                data[_team_label(str(t))][topic] += 1

    if not data:
        print("No hasTopic triples found — rebuild the graph first.")
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
    print(f"  -> {OUT / 'topics_by_team.png'}")

    for team in sorted(data):
        top3 = sorted(data[team].items(), key=lambda x: -x[1])[:3]
        print(f"    {team}: " + ", ".join(f"{t} ({c})" for t, c in top3))


def analyse_topics_over_time(g, top_n=8):
    data = defaultdict(lambda: defaultdict(int))
    for pub in g.subjects(RDF.type, LRE.Publication):
        topic_node = g.value(pub, LRE.hasTopic)
        year_node = g.value(pub, LRE.inYear)
        if topic_node is None or year_node is None:
            continue
        topic = str(g.value(topic_node, DCTERMS.title) or "Unknown")
        yr = _year_label(str(year_node))
        data[yr][topic] += 1

    if not data:
        return

    total = defaultdict(int)
    for yr_data in data.values():
        for topic, c in yr_data.items():
            total[topic] += c
    top_topics = [t for t, _ in sorted(total.items(), key=lambda x: -x[1])[:top_n]]

    years = sorted(data)
    colors = cm.tab10(np.linspace(0, 1, len(top_topics)))

    fig, ax = plt.subplots(figsize=(13, 5))
    for i, topic in enumerate(top_topics):
        counts = [data[yr].get(topic, 0) for yr in years]
        ax.plot(years, counts, "o-", label=topic, color=colors[i], linewidth=1.5, markersize=4)
    ax.set_title(f"Top {top_n} topics over time", fontsize=13)
    ax.set_xlabel("Year")
    ax.set_ylabel("Publications")
    ax.legend(fontsize=7, ncol=2)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "topics_over_time.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'topics_over_time.png'}")

    recent_years = [y for y in years if int(y) >= 2020]
    if recent_years:
        recent_totals = {t: sum(data[y].get(t, 0) for y in recent_years) for t in top_topics}
        emerging = max(recent_totals, key=recent_totals.get)
        print(f"    Most active topic since 2020: {emerging} ({recent_totals[emerging]} pubs)")


def analyse_collab_growth(g):
    lre_members = set(g.subjects(LRE.memberOf, None))
    member_team = {r: _team_label(str(g.value(r, LRE.memberOf)))
                   for r in lre_members if g.value(r, LRE.memberOf)}

    year_same = defaultdict(set)
    year_cross = defaultdict(set)
    year_external = defaultdict(set)

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
                    if member_team.get(la) == member_team.get(lb):
                        year_same[yr].add((str(la), str(lb)))
                    else:
                        year_cross[yr].add((str(la), str(lb)))
            for ea in ext_authors:
                year_external[yr].add((str(la), str(ea)))

    all_years = set(year_same) | set(year_cross) | set(year_external)
    years = sorted(y for y in all_years if y.isdigit() and 1990 <= int(y) <= 2025)
    if not years:
        return

    same_counts  = [len(year_same.get(y, set())) for y in years]
    cross_counts = [len(year_cross.get(y, set())) for y in years]
    ext_counts   = [len(year_external.get(y, set())) for y in years]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(years, same_counts,  "o-",  color="#4363D8", label="Within-team (LRE)",  linewidth=2)
    ax.plot(years, cross_counts, "s--", color="#3CB44B", label="Cross-team (LRE)",   linewidth=2)
    ax.plot(years, ext_counts,   "^:",  color="#E6194B", label="LRE-external",        linewidth=2)
    ax.set_title("Collaboration pairs per year", fontsize=14)
    ax.set_xlabel("Year")
    ax.set_ylabel("Co-authorship pairs")
    ax.legend()
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "collab_growth.png", dpi=150)
    plt.close(fig)
    print(f"  -> {OUT / 'collab_growth.png'}")

def main():
    print("Loading graph …")
    g = load_graph()

    print("\n[1] Publications per year")
    analyse_pubs_per_year(g)

    print("\n[2] Publications per team")
    analyse_pubs_per_team(g)

    print("\n[3] Top researchers")
    analyse_top_researchers(g)

    print("\n[4] Co-authorship network")
    G = analyse_coauthor_network(g)

    print("\n[5] Betweenness centrality")
    analyse_betweenness(G)

    print("\n[6] Team collaboration heatmap")
    analyse_team_heatmap(g)

    print("\n[7] Topics by team")
    analyse_topics_by_team(g)

    print("\n[8] Topics over time")
    analyse_topics_over_time(g)

    print("\n[9] Collaboration growth over time")
    analyse_collab_growth(g)
    print(f"\nAll figures saved to {OUT}/")


if __name__ == "__main__":
    main()
