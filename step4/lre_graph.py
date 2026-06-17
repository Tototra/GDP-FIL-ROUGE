import urllib.parse

from rdflib import Graph, Namespace, RDF, Literal, URIRef, OWL
from rdflib.namespace import FOAF, DCTERMS, XSD

LRE = Namespace("http://lre.epita.fr/kg/")


class LREGraph:
    def __init__(self):
        self.g = Graph()
        self.g.bind("lre", LRE)
        self.g.bind("foaf", FOAF)
        self.g.bind("dcterms", DCTERMS)
        self.g.bind("owl", OWL)

    def add_team(self, team):
        team_node = LRE[f"team_{team}"]
        self.g.add((team_node, RDF.type, LRE.Team))
        return team_node

    def add_researcher(self, pid, name, team, year):
        safe_pid = str(pid).replace("_", "/")
        p = LRE[f"person_{pid}"]
        self.g.add((p, RDF.type, LRE.Researcher))
        self.g.add((p, FOAF.name, Literal(name)))

        safe_team = urllib.parse.quote(str(team).replace(" ", "_"))

        try:
            self.g.add((p, LRE.arrivalYear, Literal(int(year), datatype=XSD.gYear)))
        except ValueError:
            pass

        dblp_uri = URIRef(f"https://dblp.org/pid/{safe_pid}")
        self.g.add((p, LRE.dblpPage, dblp_uri))
        self.g.add((p, OWL.sameAs, dblp_uri))
        self.g.add((p, LRE.memberOf, self.add_team(safe_team)))
        return p

    def add_publication(self, pid, author, coauthors, title, topic, venue, year, url="", max_coauthors=20):
        if str(venue[1]).strip().lower() == "corr":
            return
        if len(coauthors) > max_coauthors:
            return

        safe_pid = str(pid).replace("/", "_")
        p_author = LRE[f"person_{safe_pid}"]

        safe_title = urllib.parse.quote(str(title).replace(" ", "_")[:50])
        pub = LRE[f"pub_{safe_title}"]

        self.g.add((pub, RDF.type, LRE.Publication))
        self.g.add((pub, DCTERMS.title, Literal(title)))
        self.g.add((pub, LRE.authoredBy, p_author))
        if url:
            self.g.add((pub, LRE.url, Literal(url)))

        safe_topic = urllib.parse.quote(str(topic).replace(" ", "_"))
        top = LRE[f"topic_{safe_topic}"]
        self.g.add((top, RDF.type, LRE.Topic))
        self.g.add((top, DCTERMS.title, Literal(topic)))
        self.g.add((pub, LRE.hasTopic, top))

        for co in coauthors:
            safe_co = urllib.parse.quote(str(co[0]).replace("/", "_"))
            p_co = LRE[f"person_{safe_co}"]
            self.g.add((p_co, RDF.type, LRE.Researcher))
            self.g.add((p_co, FOAF.name, Literal(co[1])))
            self.g.add((pub, LRE.authoredBy, p_co))
            self.g.add((p_author, LRE.coAuthorOf, p_co))
            self.g.add((p_co, LRE.coAuthorOf, p_author))

        safe_venue = urllib.parse.quote(str(venue[1]).replace(" ", "_")[:50])
        v = LRE[f"venue_{safe_venue}"]
        self.g.add((v, RDF.type, LRE.Venue))
        self.g.add((v, LRE.source, Literal(venue[0])))
        self.g.add((v, DCTERMS.title, Literal(venue[1])))
        self.g.add((pub, LRE.publishedIn, v))

        y = LRE[f"year_{year}"]
        self.g.add((y, RDF.type, LRE.Year))
        self.g.add((pub, LRE.inYear, y))
