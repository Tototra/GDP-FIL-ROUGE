from collections import defaultdict

import networkx as nx
import numpy as np
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import FOAF, DCTERMS

LRE = Namespace("http://lre.epita.fr/kg/")


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


def team_collab_matrix(g: Graph, teams: list[str]) -> np.ndarray:
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
    return mat


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
