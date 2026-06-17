import json
import re
import urllib.parse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, jsonify, render_template, request, send_file
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import FOAF, DCTERMS
from pyvis.network import Network
from export_full import build_full_html

LRE = Namespace("http://lre.epita.fr/kg/")
TTL_PATH     = Path(__file__).parent.parent / "output" / "lre_kg.ttl"
FULL_HTML    = Path(__file__).parent.parent / "output" / "lre_kg.html"
OVERVIEW_HTML = Path(__file__).parent.parent / "output" / "lre_kg_full.html"
QUERIES_FILE  = Path(__file__).parent.parent / "step9"  / "queries.rq"
METRICS_FILE  = Path(__file__).parent.parent / "step10" / "metrics.txt"
PREDICTIONS_FILE = Path(__file__).parent.parent / "step10" / "predictions.json"

TEAM_COLORS = [
    "#E6194B", "#3CB44B", "#4363D8", "#F58231",
    "#911EB4", "#42D4F4", "#F032E6", "#469990",
    "#BFEF45", "#FFE119",
]

app = Flask(__name__)
_rdf_graph: Graph | None = None
_query_cache: list | None = None


def get_graph() -> Graph:
    global _rdf_graph
    if _rdf_graph is None:
        _rdf_graph = Graph()
        _rdf_graph.parse(str(TTL_PATH), format="turtle")
    return _rdf_graph


def build_team_colors(g: Graph) -> dict[str, str]:
    teams = sorted({
        str(t).split("team_")[-1]
        for t in g.objects(None, LRE.memberOf)
    })
    return {team: TEAM_COLORS[i % len(TEAM_COLORS)] for i, team in enumerate(teams)}


def _decode_team(raw: str) -> str:
    return urllib.parse.unquote(raw).replace("_", " ")


def _parse_queries(text: str) -> list[tuple[str, str]]:
    blocks = []
    pattern = re.compile(r"(#\s*Q\d+[^\n]*\n)(.*?)(?=\n#\s*Q\d+|\Z)", re.DOTALL)
    for m in pattern.finditer(text):
        title = m.group(1).strip().lstrip("# ")
        body  = m.group(2).strip()
        if "SELECT" in body.upper():
            blocks.append((title, body))
    return blocks


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/researchers")
def api_researchers():
    g = get_graph()
    names = sorted({
        str(g.value(p, FOAF.name))
        for p in g.subjects(RDF.type, LRE.Researcher)
        if g.value(p, FOAF.name) and g.value(p, LRE.memberOf)
    })
    return jsonify(names)


@app.route("/full")
def full_graph():
    if not FULL_HTML.exists():
        return "Graphe non généré. Lance d'abord : python step7/export_gephi.py", 404
    return send_file(str(FULL_HTML))


@app.route("/overview")
def overview():
    build_full_html(str(TTL_PATH), str(OVERVIEW_HTML))
    return send_file(str(OVERVIEW_HTML))


@app.route("/stats")
def stats():
    return render_template("stats.html")


@app.route("/api/stats")
def api_stats():
    g = get_graph()
    PFX = """
    PREFIX lre:     <http://lre.epita.fr/kg/>
    PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    """

    yearly = {str(r.year): int(r.n) for r in g.query(PFX + """
        SELECT ?year (COUNT(DISTINCT ?pub) AS ?n) WHERE {
          ?pub rdf:type lre:Publication ; lre:inYear ?y .
          BIND(STRAFTER(STR(?y),"year_") AS ?year)
        } GROUP BY ?year ORDER BY ?year""")}

    teams = [{"team": _decode_team(str(r.team)), "count": int(r.n)}
             for r in g.query(PFX + """
        SELECT ?team (COUNT(DISTINCT ?pub) AS ?n) WHERE {
          ?pub rdf:type lre:Publication ; lre:authoredBy ?r .
          ?r lre:memberOf ?t .
          BIND(STRAFTER(STR(?t),"team_") AS ?team)
        } GROUP BY ?team ORDER BY DESC(?n)""")]

    top_res = [{"name": str(r.name), "team": _decode_team(str(r.team)), "count": int(r.n)}
               for r in g.query(PFX + """
        SELECT ?name ?team (COUNT(DISTINCT ?pub) AS ?n) WHERE {
          ?r rdf:type lre:Researcher ; foaf:name ?name ; lre:memberOf ?t .
          BIND(STRAFTER(STR(?t),"team_") AS ?team)
          ?pub lre:authoredBy ?r .
        } GROUP BY ?name ?team ORDER BY DESC(?n) LIMIT 15""")]

    venues = [{"venue": str(r.venue), "count": int(r.n)}
              for r in g.query(PFX + """
        SELECT ?venue (COUNT(DISTINCT ?pub) AS ?n) WHERE {
          ?pub rdf:type lre:Publication ; lre:publishedIn ?v .
          ?v dcterms:title ?venue .
        } GROUP BY ?venue ORDER BY DESC(?n) LIMIT 10""")]

    topics: dict = {}
    try:
        for r in g.query(PFX + """
            SELECT ?team ?topic (COUNT(DISTINCT ?pub) AS ?n) WHERE {
              ?pub rdf:type lre:Publication ; lre:hasTopic ?top ; lre:authoredBy ?r .
              ?r lre:memberOf ?t .
              ?top dcterms:title ?topic .
              BIND(STRAFTER(STR(?t),"team_") AS ?team)
            } GROUP BY ?team ?topic ORDER BY ?team DESC(?n)"""):
            t = _decode_team(str(r.team))
            topics.setdefault(t, {})[str(r.topic)] = int(r.n)
    except Exception:
        pass

    return jsonify({"yearly": yearly, "teams": teams,
                    "top_researchers": top_res, "venues": venues, "topics": topics})


@app.route("/queries")
def queries_page():
    return render_template("queries.html")


@app.route("/api/queries")
def api_queries():
    global _query_cache
    if _query_cache is not None:
        return jsonify(_query_cache)

    g = get_graph()
    if not QUERIES_FILE.exists():
        return jsonify([])

    raw = QUERIES_FILE.read_text(encoding="utf-8")
    parsed = _parse_queries(raw)

    PFX = ("PREFIX lre: <http://lre.epita.fr/kg/>\n"
           "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
           "PREFIX dcterms: <http://purl.org/dc/terms/>\n"
           "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")

    results = []
    for title, sparql in parsed:
        clean = re.sub(r"^PREFIX\s+\S+\s+<[^>]+>\s*", "", sparql, flags=re.MULTILINE).strip()
        try:
            qr = g.query(PFX + clean)
            rows = [[str(v) if v is not None else "" for v in row] for row in qr]
            headers = [str(v) for v in qr.vars]
            results.append({"name": title, "sparql": sparql,
                            "headers": headers, "rows": rows, "error": None})
        except Exception as e:
            results.append({"name": title, "sparql": sparql,
                            "headers": [], "rows": [], "error": str(e)})

    _query_cache = results
    return jsonify(results)


@app.route("/links")
def links_page():
    metrics = None
    predictions = None
    if METRICS_FILE.exists():
        metrics = METRICS_FILE.read_text(encoding="utf-8")
    if PREDICTIONS_FILE.exists():
        predictions = json.loads(PREDICTIONS_FILE.read_text(encoding="utf-8"))
    return render_template("links.html", metrics=metrics, predictions=predictions)


@app.route("/focus")
def focus():
    query = request.args.get("name", "").strip().lower()
    g = get_graph()
    team_color = build_team_colors(g)

    matches = [
        person for person in g.subjects(RDF.type, LRE.Researcher)
        if query in str(g.value(person, FOAF.name) or "").lower()
    ]

    if not matches:
        return render_template("focus.html", name=query, found=False,
                               graph_html="", publications=[])

    center = next(
        (p for p in matches if str(g.value(p, FOAF.name) or "").lower() == query),
        matches[0]
    )
    center_name = str(g.value(center, FOAF.name) or str(center).split("person_")[-1])

    neighbors = {str(o) for _, _, o in g.triples((center, LRE.coAuthorOf, None))}
    neighbors |= {str(s) for s, _, _ in g.triples((None, LRE.coAuthorOf, center))}
    all_nodes = {str(center)} | neighbors

    net = Network(height="calc(100vh - 52px)", width="100%", bgcolor="#1a1a2e", font_color="white")

    degree_in_ego: dict[str, int] = {}
    for s, _, o in g.triples((None, LRE.coAuthorOf, None)):
        if str(s) in all_nodes:
            degree_in_ego[str(s)] = degree_in_ego.get(str(s), 0) + 1
    max_deg = max(degree_in_ego.values(), default=1)

    for node_uri_str in all_nodes:
        node_uri = URIRef(node_uri_str)
        name_val  = g.value(node_uri, FOAF.name)
        team_uri  = g.value(node_uri, LRE.memberOf)
        team_label = str(team_uri).split("team_")[-1] if team_uri else "unknown"
        team_display = _decode_team(team_label) if team_label != "unknown" else "Externe"
        label = str(name_val) if name_val else node_uri_str.split("person_")[-1]
        is_center = node_uri_str == str(center)
        color = "#FFE119" if is_center else team_color.get(team_label, "#888888")
        deg   = degree_in_ego.get(node_uri_str, 0)
        size  = (22 + (deg / max_deg) * 45) if is_center else (10 + (deg / max_deg) * 20)
        year_val = g.value(node_uri, LRE.arrivalYear)
        year_line = f"\nArrivée : {year_val}" if year_val and is_center else ""
        tooltip = f"{label}\nEquipe : {team_display}\n{deg} co-auteur(s){year_line}"
        net.add_node(node_uri_str, label=label,
                     color={"background": color, "border": "#fff" if is_center else color},
                     size=size, title=tooltip, borderWidth=2 if is_center else 1)

    seen: set[frozenset] = set()
    for s, _, o in g.triples((None, LRE.coAuthorOf, None)):
        src, dst = str(s), str(o)
        if src not in all_nodes or dst not in all_nodes:
            continue
        key = frozenset([src, dst])
        if key in seen:
            continue
        seen.add(key)
        is_ego = src == str(center) or dst == str(center)
        net.add_edge(src, dst, title="coAuthorOf",
                     color="#FFE119aa" if is_ego else "#ffffff22",
                     width=2 if is_ego else 1)

    net.set_options("""{
      "nodes":{"font":{"size":13,"face":"Segoe UI"}},
      "edges":{"smooth":{"type":"continuous"}},
      "interaction":{"hover":true,"tooltipDelay":80,"navigationButtons":true,"keyboard":true},
      "physics":{"barnesHut":{"gravitationalConstant":-18000,"centralGravity":0.1,
        "springLength":280,"springConstant":0.03,"damping":0.15},
        "stabilization":{"iterations":250}}
    }""")

    center_pubs = []
    for pub, _, _ in g.triples((None, LRE.authoredBy, center)):
        title = str(g.value(pub, DCTERMS.title) or "Sans titre")
        year_node = g.value(pub, LRE.inYear)
        year  = str(year_node).split("year_")[-1] if year_node else "?"
        venue_node = g.value(pub, LRE.publishedIn)
        venue = str(g.value(venue_node, DCTERMS.title) or "") if venue_node else ""
        url   = str(g.value(pub, LRE.url) or "")
        center_pubs.append({"title": title, "year": year, "venue": venue, "url": url})
    center_pubs.sort(key=lambda x: x["year"], reverse=True)

    html_content = net.generate_html()
    inner = (html_content.replace("<!DOCTYPE html>", "")
             .replace("<html>", "").replace("</html>", ""))

    return render_template("focus.html", name=center_name, found=True,
                           graph_html=inner, publications=center_pubs)


@app.route("/api/common")
def api_common():
    uri_a = request.args.get("a", "")
    uri_b = request.args.get("b", "")
    if not uri_a or not uri_b:
        return jsonify([])
    g = get_graph()
    pubs_a = {str(s) for s, _, _ in g.triples((None, LRE.authoredBy, URIRef(uri_a)))}
    pubs_b = {str(s) for s, _, _ in g.triples((None, LRE.authoredBy, URIRef(uri_b)))}
    results = []
    for pub_uri in pubs_a & pubs_b:
        pub = URIRef(pub_uri)
        title = str(g.value(pub, DCTERMS.title) or "Sans titre")
        year_node = g.value(pub, LRE.inYear)
        year  = str(year_node).split("year_")[-1] if year_node else "?"
        venue_node = g.value(pub, LRE.publishedIn)
        venue = str(g.value(venue_node, DCTERMS.title) or "") if venue_node else ""
        url   = str(g.value(pub, LRE.url) or "")
        results.append({"title": title, "year": year, "venue": venue, "url": url})
    results.sort(key=lambda x: x["year"], reverse=True)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
