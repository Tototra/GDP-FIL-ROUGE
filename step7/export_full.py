import math
import urllib.parse
from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import FOAF, DCTERMS
from pyvis.network import Network

LRE = Namespace("http://lre.epita.fr/kg/")

TEAM_COLORS = [
    "#E6194B", "#3CB44B", "#4363D8", "#F58231",
    "#911EB4", "#42D4F4", "#F032E6", "#469990",
    "#BFEF45", "#FFE119",
]

INJECTED_CSS = """<style>
div.vis-tooltip {
  background: rgba(15,52,96,0.97) !important;
  border: 1px solid #42D4F4 !important;
  border-radius: 10px !important;
  padding: 10px 15px !important;
  font-family: 'Segoe UI', sans-serif !important;
  font-size: 13px !important;
  color: #eee !important;
  line-height: 1.8 !important;
  white-space: pre-line !important;
  box-shadow: 0 6px 24px rgba(0,0,0,.6) !important;
  pointer-events: none !important;
  max-width: 300px !important;
}
#legend {
  position: fixed; bottom: 18px; left: 18px; z-index: 500;
  background: rgba(15,52,96,0.92); border: 1px solid #42D4F4;
  border-radius: 10px; padding: 12px 16px;
  font-family: 'Segoe UI', sans-serif; font-size: 12px; color: #eee;
  line-height: 2.1; pointer-events: none;
}
#legend strong { color: #42D4F4; display: block; margin-bottom: 4px; font-size: 13px; }
.leg-row { display: flex; align-items: center; gap: 8px; }
.leg-dot  { width:12px; height:12px; border-radius:50%; border:2px solid #fff; flex-shrink:0; }
.leg-sq   { width:10px; height:10px; border-radius:2px; flex-shrink:0; }
</style>
<div id="legend">
  <strong>Légende</strong>
  <div class="leg-row"><span class="leg-dot" style="background:#4DA6FF"></span> Chercheur LRE</div>
  <div class="leg-row"><span class="leg-dot" style="background:#2a2a4a;border-color:#666"></span> Co-auteur externe</div>
  <div class="leg-row"><span class="leg-sq"  style="background:#1a4a8a;border:1px solid #42D4F4"></span> Publication (cliquer pour ouvrir)</div>
  <div class="leg-row"><span class="leg-sq" style="background:none;border:none;font-size:13px;width:auto">★</span> Équipe</div>
</div>"""


def _decode_team(raw: str) -> str:
    return urllib.parse.unquote(raw).replace("_", " ")


def build_full_html(ttl_path: str, output_path: str):
    g = Graph()
    g.parse(ttl_path, format="turtle")

    teams = sorted({
        str(t).split("team_")[-1]
        for t in g.objects(None, LRE.memberOf)
    })
    team_color = {t: TEAM_COLORS[i % len(TEAM_COLORS)] for i, t in enumerate(teams)}

    lre_set = {
        str(p) for p in g.subjects(RDF.type, LRE.Researcher)
        if g.value(p, LRE.memberOf)
    }

    net = Network(height="100vh", width="100%", bgcolor="#0d0d1a", font_color="white")

    # Team nodes, fixed in a circle
    n = len(teams)
    for i, team in enumerate(teams):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = math.cos(angle) * 900
        y = math.sin(angle) * 900
        color = team_color[team]
        label = _decode_team(team)
        net.add_node(
            f"__team__{team}",
            label=label, shape="star",
            color={"background": color, "border": "#ffffff"},
            size=40,
            font={"size": 16, "color": "#ffffff", "bold": True},
            title=f"★  Équipe {label}",
            x=x, y=y, fixed=True,
        )

    # LRE researcher nodes
    for person in g.subjects(RDF.type, LRE.Researcher):
        uri = str(person)
        if uri not in lre_set:
            continue
        name = str(g.value(person, FOAF.name) or uri.split("person_")[-1])
        team_uri = g.value(person, LRE.memberOf)
        team_key = str(team_uri).split("team_")[-1] if team_uri else teams[0]
        color = "#4DA6FF"
        arrival = g.value(person, LRE.arrivalYear)
        tooltip = (
            f"{name}\n"
            f"Equipe : {_decode_team(team_key)}"
            + (f"\nArrivée : {arrival}" if arrival else "")
        )
        net.add_node(
            uri, label=name, shape="dot",
            color={"background": color, "border": "#ffffff"},
            size=18,
            font={"size": 12, "color": "#ffffff"},
            title=tooltip, mass=3,
        )
        if team_uri:
            net.add_edge(uri, f"__team__{team_key}",
                         color="#4DA6FF88", width=1.5, title="memberOf")

    # Publications + co-auteurs externes (structure : externe → pub → LRE)
    node_ids: set[str] = {f"__team__{t}" for t in teams} | lre_set
    added_ext: set[str] = set()

    for pub in g.subjects(RDF.type, LRE.Publication):
        pub_str = str(pub)
        all_authors = [(str(o), g.value(URIRef(str(o)), FOAF.name))
                       for _, _, o in g.triples((pub, LRE.authoredBy, None))]
        lre_authors  = [(uri, nm) for uri, nm in all_authors if uri in lre_set]
        ext_authors  = [(uri, nm) for uri, nm in all_authors if uri not in lre_set]

        if not lre_authors:
            continue

        title     = str(g.value(pub, DCTERMS.title) or "?")
        year_node = g.value(pub, LRE.inYear)
        year      = str(year_node).split("year_")[-1] if year_node else "?"
        venue_node = g.value(pub, LRE.publishedIn)
        venue = str(g.value(venue_node, DCTERMS.title) or "") if venue_node else ""
        tooltip = (
            f"{title[:80]}\nAnnée : {year}"
            + (f"\nVenue : {venue[:50]}" if venue else "")
        )
        short_title = title[:28] + "…" if len(title) > 28 else title
        pub_url = str(g.value(pub, LRE.url) or "")
        net.add_node(
            pub_str, label=short_title, shape="square",
            color={"background": "#1a4a8a", "border": "#42D4F466"},
            size=6, title=tooltip, mass=0.4,
            font={"size": 8, "color": "#aaccff"},
            url=pub_url,
        )
        node_ids.add(pub_str)

        # Publication → auteur LRE
        for lre_uri, _ in lre_authors:
            net.add_edge(pub_str, lre_uri,
                         color="#42D4F430", width=0.8, title="authoredBy")

        # Co-auteur externe → Publication
        for ext_uri, ext_name in ext_authors:
            name = str(ext_name or ext_uri.split("person_")[-1])
            if ext_uri not in added_ext:
                net.add_node(
                    ext_uri, label=name, shape="dot",
                    color={"background": "#2a2a4a", "border": "#666666"},
                    size=8, font={"size": 10, "color": "#aaaaaa"},
                    title=f"{name}\nCo-auteur externe",
                    mass=1,
                )
                added_ext.add(ext_uri)
                node_ids.add(ext_uri)
            net.add_edge(ext_uri, pub_str,
                         color="#ffffff18", width=0.5, title="co-auteur")

    net.set_options("""
    {
      "nodes": { "font": { "face": "Segoe UI" } },
      "edges": { "smooth": { "type": "continuous" } },
      "interaction": {
        "hover": true, "tooltipDelay": 80,
        "navigationButtons": true, "keyboard": true,
        "dragNodes": false
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -22000,
          "centralGravity": 0.05,
          "springLength": 220,
          "springConstant": 0.04,
          "damping": 0.2,
          "avoidOverlap": 0.4
        },
        "stabilization": { "iterations": 300, "fit": true }
      }
    }
    """)

    # Build a JS map of nodeId → url for publication nodes
    url_map_js = "const PUB_URLS = " + "{" + ",".join(
        f'"{str(pub)}":"{str(g.value(pub, LRE.url) or "")}"'
        for pub in g.subjects(RDF.type, LRE.Publication)
        if g.value(pub, LRE.url)
    ) + "};\n"

    click_js = """<script>
""" + url_map_js + """
document.addEventListener('DOMContentLoaded', function() {
  var checkReady = setInterval(function() {
    if (typeof network !== 'undefined') {
      clearInterval(checkReady);
      network.on('click', function(params) {
        if (params.nodes.length === 1) {
          var nodeId = params.nodes[0];
          if (PUB_URLS[nodeId]) {
            window.open(PUB_URLS[nodeId], '_blank');
          }
        }
      });
    }
  }, 200);
});
</script>"""

    html_content = net.generate_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(INJECTED_CSS + html_content + click_js)

    print(
        f"Overview: {len(teams)} équipes · {len(lre_set)} LRE · "
        f"{len(added_ext)} externes · "
        f"{sum(1 for _ in g.subjects(RDF.type, LRE.Publication))} publications"
        f" → {output_path}"
    )


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    build_full_html(
        str(root / "output" / "lre_kg.ttl"),
        str(root / "output" / "lre_kg_full.html"),
    )
