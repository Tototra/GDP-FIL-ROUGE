from rdflib import Graph, Namespace, RDF
from rdflib.namespace import FOAF
from pyvis.network import Network

LRE = Namespace("http://lre.epita.fr/kg/")

TEAM_COLORS = [
    "#E6194B",  # red
    "#3CB44B",  # green
    "#4363D8",  # blue
    "#F58231",  # orange
    "#911EB4",  # purple
    "#42D4F4",  # cyan
    "#F032E6",  # magenta
    "#469990",  # teal
    "#BFEF45",  # lime
    "#FFE119",  # yellow
]


def rdf_to_html(ttl_path: str, output_path: str):
    g = Graph()
    g.parse(ttl_path, format="turtle")

    teams = sorted({
        str(t).split("team_")[-1]
        for t in g.objects(None, LRE.memberOf)
    })
    team_color = {
        team: TEAM_COLORS[i % len(TEAM_COLORS)]
        for i, team in enumerate(teams)
    }

    # Count co-authorship degree for node sizing
    degree: dict[str, int] = {}
    for s, _, o in g.triples((None, LRE.coAuthorOf, None)):
        degree[str(s)] = degree.get(str(s), 0) + 1

    max_deg = max(degree.values(), default=1)

    net = Network(height="900px", width="100%", bgcolor="#1a1a2e", font_color="white")
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    added_nodes: set[str] = set()

    for person in g.subjects(RDF.type, LRE.Researcher):
        node_id = str(person)
        name = g.value(person, FOAF.name)
        team_uri = g.value(person, LRE.memberOf)
        team_label = str(team_uri).split("team_")[-1] if team_uri else "unknown"

        label = str(name) if name else node_id.split("person_")[-1]
        color = team_color.get(team_label, "#888888")
        deg = degree.get(node_id, 0)
        size = 10 + (deg / max_deg) * 40

        tooltip = f"<b>{label}</b><br>Team: {team_label}<br>Co-authors: {deg}"
        year = g.value(person, LRE.arrivalYear)
        if year:
            tooltip += f"<br>Arrival: {year}"

        net.add_node(node_id, label=label, color=color, size=size, title=tooltip)
        added_nodes.add(node_id)

    seen_edges: set[frozenset] = set()
    for s, _, o in g.triples((None, LRE.coAuthorOf, None)):
        src, dst = str(s), str(o)
        if src not in added_nodes or dst not in added_nodes:
            continue
        key = frozenset([src, dst])
        if key in seen_edges:
            continue
        seen_edges.add(key)
        net.add_edge(src, dst, title="coAuthorOf", color="#ffffff44")

    # Legend as an extra node group (visual only)
    net.set_options("""
    {
      "nodes": { "font": { "size": 14 } },
      "edges": { "smooth": { "type": "continuous" } },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 150
        },
        "stabilization": { "iterations": 200 }
      }
    }
    """)

    net.save_graph(output_path)
    print(f"Graph: {len(added_nodes)} nodes, {len(seen_edges)} edges → {output_path}")
    print("Teams:")
    for team, color in team_color.items():
        print(f"  {team}: {color}")


if __name__ == "__main__":
    rdf_to_html("output/lre_kg.ttl", "output/lre_kg.html")
