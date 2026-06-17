#set document(title: "LRE Knowledge Graph & Link Prediction", author: "Yako Lemeilleur, Thomas Trahant")
#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(size: 9pt, fill: luma(140))
      #grid(
        columns: (1fr, 1fr),
        align(left)[LRE Knowledge Graph],
        align(right)[EPITA — MGD 2025–2026],
      )
      #line(length: 100%, stroke: 0.4pt + luma(180))
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #line(length: 100%, stroke: 0.4pt + luma(180))
      #set text(size: 9pt, fill: luma(140))
      #align(center)[#counter(page).display("1 / 1", both: true)]
    ]
  },
)
#set text(font: "New Computer Modern", size: 11pt, lang: "fr")
#set par(justify: true, leading: 0.78em)
#set heading(numbering: "1.1")

#show raw.where(block: true): it => block(
  fill: luma(245),
  stroke: 0.5pt + luma(200),
  radius: 5pt,
  inset: 12pt,
  width: 100%,
  text(size: 9pt, it),
)
#show raw.where(block: false): it => box(
  fill: luma(235),
  radius: 3pt,
  inset: (x: 4pt, y: 1pt),
  text(size: 9pt, it),
)

#let note(body) = block(
  fill: rgb("#eef6ff"),
  stroke: (left: 3pt + rgb("#4363D8")),
  radius: (right: 4pt),
  inset: 10pt,
  width: 100%,
)[#body]

#let warn(body) = block(
  fill: rgb("#fff8e1"),
  stroke: (left: 3pt + rgb("#F58231")),
  radius: (right: 4pt),
  inset: 10pt,
  width: 100%,
)[#body]


#page(header: none, footer: none)[
  #v(3cm)
  #align(center)[
    #text(size: 13pt, fill: luma(100))[EPITA · Master Grande École · MGD 2025–2026]
    #v(1.5cm)
    #text(size: 28pt, weight: "bold")[LRE Knowledge Graph]
    #v(0.4cm)
    #text(size: 20pt, fill: rgb("#4363D8"))[& Link Prediction]
    #v(1cm)
    #line(length: 60%, stroke: 2pt + rgb("#4363D8"))
    #v(1cm)
    #text(size: 13pt, fill: luma(80))[
      Construction d'un graphe de connaissances sur les membres #linebreak()
      du laboratoire LRE à partir des données DBLP — #linebreak()
      ontologie OWL, analyse de réseau, requêtes SPARQL #linebreak()
      et prédiction de liens avec PyKEEN.
    ]
    #v(3cm)
    #grid(
      columns: (1fr, 1fr),
      gutter: 1cm,
      align(center)[
        #text(weight: "bold")[Équipe]
        #v(0.3cm)
        _Yako Lemeilleur_\
        _Thomas Trahant_
      ],
      align(center)[
        #text(weight: "bold")[Dépôt]
        #v(0.3cm)
        `gitlab.cri.epita.fr`\
        `yako.lemeilleur/lre-kglp`
      ],
    )
    #v(3cm)
    #text(size: 10pt, fill: luma(130))[Juin 2026]
  ]
]

#outline(depth: 2, indent: 1.5em)
#pagebreak()


= Introduction

L'idée de ce projet, c'est de construire un *graphe de connaissances* à partir des publications des chercheurs du laboratoire LRE d'EPITA. On a utilisé DBLP comme source principale — c'est une base bibliographique publique qui recense pratiquement tout ce qui se publie en informatique, et qui propose une API XML très pratique.

À partir de ces données, on a construit un graphe RDF, écrit une ontologie OWL, fait quelques requêtes SPARQL pour explorer le graphe, analysé le réseau de co-authorship, et finalement appliqué des modèles d'embedding pour essayer de prédire des collaborations futures entre chercheurs.

Les dix étapes du projet sont terminées. Le graphe final contient *18 475 triplets*, couvre 47 chercheurs LRE et plus de 1 100 publications.

== Sources de données

Deux sources sont utilisées :

- *DBLP* (`https://dblp.org/pid/{PID}.xml`) : la bibliographie complète de chaque chercheur au format XML. C'est gratuit, pas besoin d'API key, et les données sont assez propres.
- *`data/ec.csv`* : un fichier fourni avec le projet listant les membres LRE avec leur équipe et leur année d'arrivée au labo.

Le graphe utilise le namespace `http://lre.epita.fr/kg/` (préfixe `lre:`) et réutilise `foaf:`, `dcterms:`, `owl:` et `xsd:` pour les parties standard.

#pagebreak()


= Step 1 — Collecte des données

Le notebook `step1/collect_data.ipynb` parcourt le CSV, reconstruit les URLs DBLP et télécharge les XML pour chaque chercheur. On a ajouté un délai de 0.5 seconde entre les requêtes pour ne pas spammer le serveur DBLP — c'est mentionné dans leur politique d'utilisation et c'est une bonne habitude de toute façon.

```python
for _, row in df.iterrows():
    pids = ast.literal_eval(row["dblp_pids"])
    for pid in pids:
        url = f"https://dblp.org/pid/{pid}.xml"
        resp = requests.get(url, timeout=30)
        safe = pid.replace("/", "_")
        Path(f"data/raw/author_{safe}.xml").write_text(resp.text)
        time.sleep(0.5)
```

Au total, 47 fichiers XML sont stockés dans `data/raw/`. Le nettoyage du CSV (step 2) a consisté surtout à gérer les PIDs multiples (certains chercheurs ont publié sous plusieurs noms ou ont plusieurs profils DBLP) et à uniformiser les noms d'équipes.

#pagebreak()


= Step 4 — Construction du graphe RDF

== Vue d'ensemble du pipeline

Le pipeline de construction se fait en trois fichiers distincts :

- `step4/dblp_parser.py` : parse les XML et extrait les informations utiles (titre, co-auteurs, venue, année, topic)
- `step4/lre_graph.py` : traduit ces données en triplets RDF via `rdflib`
- `step4/build_graph.py` : orchestre tout ça, lit le CSV, et sérialise le résultat en Turtle

== Parsing des données DBLP

Le parseur gère trois types de publications : articles de journal (`<article>`), contributions à des conférences (`<inproceedings>`) et thèses (`<phdthesis>`). Pour chaque publication, on extrait les co-auteurs, le titre, la venue et l'année.

Un choix qu'on a fait : exclure les publications avec plus de 20 co-auteurs. Ça peut paraître arbitraire, mais en pratique ces méga-articles (grands consortiums, physique des particules qui se retrouvent parfois dans les listes DBLP) ne reflètent pas vraiment des collaborations scientifiques directes, et ils gonflent artificiellement les liens de co-authorship.

== Classification des topics

Pour associer un topic à chaque publication, on utilise le modèle BERT d'OpenAlex (`bert-base-multilingual-cased-finetuned-openalex-topic-classification-title-abstract`). Ce modèle prend un titre de publication et renvoie un identifiant de topic dans la taxonomie OpenAlex, qu'on remonte ensuite jusqu'au niveau « subfield » pour avoir une granularité raisonnable.

```python
output = self.classifier("<TITLE>" + title)[0][0]["label"]
raw_topic = output.split(":")[0]
true_topic_id = str(int(raw_topic.strip()) + 10000)
if true_topic_id in self.taxonomy_map:
    return self.taxonomy_map[true_topic_id]["subfield"]
```

Comme le modèle est trop lent à charger à la volée pour 1 000+ publications, on l'a fait tourner une seule fois via `step4/topic_modelling/precompute_topics.py` et les résultats sont stockés dans `precomputed_topics.json`. Le pipeline de construction les charge directement sans re-inférer.

== Construction du graphe (`lre_graph.py`)

La classe `LREGraph` encapsule le graphe `rdflib` et expose deux méthodes principales.

Pour chaque chercheur :

```python
def add_researcher(self, pid, name, team, year):
    p = LRE[f"person_{pid}"]
    self.g.add((p, RDF.type,        LRE.Researcher))
    self.g.add((p, FOAF.name,       Literal(name)))
    self.g.add((p, LRE.arrivalYear,
                   Literal(int(year), datatype=XSD.gYear)))
    dblp_uri = URIRef(f"https://dblp.org/pid/{safe_pid}")
    self.g.add((p, LRE.dblpPage,    dblp_uri))
    self.g.add((p, OWL.sameAs,      dblp_uri))
    self.g.add((p, LRE.memberOf,    self.add_team(team)))
```

Le `owl:sameAs` relie chaque chercheur à son URI DBLP — c'est ce que demande le sujet pour le Linked Data. On fait ça au niveau des instances (pas des classes), ce qui est la bonne façon de l'utiliser.

Pour chaque publication, les co-auteurs sont reliés par `lre:coAuthorOf` dans les deux sens (relation symétrique, explicite dans le graphe et marquée comme `owl:SymmetricProperty` dans l'ontologie) :

```python
self.g.add((p_author, LRE.coAuthorOf, p_co))
self.g.add((p_co,     LRE.coAuthorOf, p_author))
```

Et pour le topic :

```python
safe_topic = urllib.parse.quote(str(topic).replace(" ", "_"))
top = LRE[f"topic_{safe_topic}"]
self.g.add((top, RDF.type,        LRE.Topic))
self.g.add((top, DCTERMS.title,   Literal(topic)))
self.g.add((pub, LRE.hasTopic,    top))
```

== Résultat

```
python step4/build_graph.py
# → output/lre_kg.ttl : 18 475 triplets
```

#pagebreak()


= Step 5 — Ontologie : classes et propriétés

L'ontologie est dans `step5/lre_onto.ttl`. On a déclaré 7 classes et une dizaine de propriétés. L'idée c'était d'être raisonnable — ne pas sur-modéliser pour quelque chose qui reste un graphe bibliographique.

== Classes

```turtle
@prefix lre:  <http://lre.epita.fr/kg/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

lre:ThingWithTopic  a owl:Class .

lre:Researcher  a owl:Class ;
    rdfs:subClassOf lre:ThingWithTopic ;
    rdfs:subClassOf foaf:Person .

lre:Publication a owl:Class ;
    rdfs:subClassOf lre:ThingWithTopic .

lre:Team   a owl:Class .
lre:Venue  a owl:Class .
lre:Topic  a owl:Class .
lre:Year   a owl:Class .
```

On a introduit `lre:ThingWithTopic` comme superclasse commune à `Researcher` et `Publication`, puisque les deux peuvent avoir un topic. En pratique seules les publications l'utilisent dans le graphe, mais ça laisse la porte ouverte.

`lre:Researcher` hérite de `foaf:Person` : c'est le genre de réutilisation de vocabulaire que le sujet encourage, et ça améliore l'interopérabilité avec d'autres outils du web sémantique.

== Propriétés objet

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 8pt,
  [*Propriété*], [*Domaine → Portée*], [*Rôle*],
  [`lre:memberOf`],     [`Researcher → Team`],           [Équipe d'appartenance],
  [`lre:authoredBy`],   [`Publication → Researcher`],    [Auteur(s) d'une publication],
  [`lre:hasAuthored`],  [`Researcher → Publication`],    [Inverse de `authoredBy`],
  [`lre:coAuthorOf`],   [`Researcher → Researcher`],     [Co-authorship (symétrique)],
  [`lre:publishedIn`],  [`Publication → Venue`],         [Lieu de publication],
  [`lre:hasTopic`],     [`ThingWithTopic → Topic`],      [Sujet de recherche],
  [`lre:inYear`],       [`Publication → Year`],          [Année],
  [`lre:dblpPage`],     [`Researcher → URI`],            [Page DBLP du chercheur],
)

== Propriétés de données

#table(
  columns: (auto, auto, auto),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 8pt,
  [*Propriété*], [*Domaine*], [*Type*],
  [`lre:arrivalYear`], [`Researcher`], [`xsd:gYear`],
  [`lre:source`],      [`Venue`],      [`xsd:string`],
)

On a utilisé `foaf:name` pour les noms (au lieu de créer `lre:name`) et `dcterms:title` pour les titres de publications et de venues. C'est plus propre de réutiliser ce qui existe.

#pagebreak()


= Step 6 — Ontologie : axiomes RDFS/OWL

L'ontologie enrichie avec les axiomes logiques est dans `step6/lre_onto.ttl`. L'objectif c'est de permettre à un raisonneur OWL d'inférer des triplets supplémentaires et de détecter des inconsistances.

== Symétrie de `coAuthorOf`

```turtle
lre:coAuthorOf a owl:ObjectProperty, owl:SymmetricProperty ;
    rdfs:domain lre:Researcher ;
    rdfs:range  lre:Researcher .
```

Dans notre graphe on stocke déjà les deux sens explicitement (A→B et B→A), donc cette déclaration ne change pas les données. Mais elle permet à un raisonneur de *vérifier* que la symétrie est bien respectée — si par erreur on avait oublié un sens, il le détecterait.

== `arrivalYear` comme propriété fonctionnelle

```turtle
lre:arrivalYear a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain lre:Researcher ;
    rdfs:range  xsd:gYear .
```

`owl:FunctionalProperty` signifie qu'un chercheur a *au plus* une année d'arrivée. Si deux valeurs différentes sont déclarées pour le même chercheur, un raisonneur détecte l'inconsistance. C'est une contrainte qui a du sens.

== Propriétés inverses

```turtle
lre:authoredBy  owl:inverseOf lre:hasAuthored .
lre:hasAuthored owl:inverseOf lre:authoredBy .
```

On ne stocke que `authoredBy` dans le graphe (publication → chercheur). Un raisonneur peut dériver automatiquement `hasAuthored` (chercheur → publication) à partir de cet axiome, sans qu'on ait besoin de stocker les deux.

== `owl:sameAs` au niveau des instances

Point un peu subtil : dans l'ontologie, on *ne met pas* `owl:sameAs` entre les classes — ça voudrait dire que les deux classes représentent exactement le même concept, ce qui serait faux. Le `owl:sameAs` est utilisé au niveau des instances, dans le graphe, pour lier chaque chercheur à son URI DBLP :

```turtle
# Dans build_graph.py — niveau instance, pas ontologie :
lre:person_237_1676 owl:sameAs <https://dblp.org/pid/237/1676> .
```

== Tableau des inférences

#table(
  columns: (1fr, 1fr),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 8pt,
  [*Axiome déclaré*], [*Ce qu'un raisonneur peut dériver*],
  [`coAuthorOf SymmetricProperty`],    [Vérification de la symétrie],
  [`arrivalYear FunctionalProperty`],  [Détection de doublons ou conflits],
  [`authoredBy inverseOf hasAuthored`],[Triplets `hasAuthored` déduits],
  [`Researcher subClassOf foaf:Person`],[Interopérabilité FOAF],
  [`domain` et `range`],               [Classification automatique des nœuds],
)

#pagebreak()


= Step 7 — Visualisation interactive

== Architecture

On a fait une interface web avec *Flask* et *pyvis* (qui génère du HTML/vis.js). L'application est dans `step7/app.py` et tourne sur `http://localhost:5050`.

Six vues sont disponibles depuis la page d'accueil :

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 8pt,
  [*Route*], [*Description*],
  [`/`],         [Accueil avec les 6 cartes de navigation],
  [`/overview`], [Graphe complet : équipes, chercheurs, externes, publications],
  [`/full`],     [Co-authorship uniquement, coloré par équipe],
  [`/focus`],    [Ego-réseau d'un chercheur avec autocomplete],
  [`/stats`],    [Statistiques et tendances (Chart.js)],
  [`/queries`],  [Résultats des 8 requêtes SPARQL],
  [`/links`],    [Métriques et prédictions de la link prediction],
)

== Vue d'ensemble

Générée par `step7/export_full.py`, elle mélange quatre types de nœuds visuellement différents : des étoiles pour les équipes (fixées en cercle comme ancres physiques), des points bleus pour les chercheurs LRE, des points gris pour les co-auteurs externes, et des petits carrés pour les publications. Les équipes sont positionnées sur un cercle avec `fixed: true` pour que le layout physique se stabilise autour d'elles.

== Vue focus

Pour un chercheur donné, on affiche son ego-réseau (lui + ses co-auteurs directs) avec un panneau latéral listant toutes ses publications. Un clic sur une arête ouvre un modal avec les publications communes entre les deux chercheurs concernés — ça marchait bien dans les tests. L'autocomplete interroge `/api/researchers` qui ne renvoie que les membres LRE (filtrés par `lre:memberOf`).

== Statistiques et requêtes

La page `/stats` calcule dynamiquement depuis le graphe et affiche cinq graphiques avec Chart.js (publications par an, par équipe, top chercheurs, venues, topics par équipe). La page `/queries` exécute les 8 requêtes SPARQL de manière asynchrone — on a dû passer par un système de cache en mémoire parce que certaines requêtes (notamment Q7 avec `FILTER NOT EXISTS`) prenaient quelques secondes et la page restait blanche.

#pagebreak()


= Step 8 — Analyse de réseau

Le script `step8/trends.py` charge le graphe TTL et construit un graphe networkx à partir des triplets `lre:coAuthorOf` entre membres LRE uniquement (on exclut les co-auteurs externes pour cette analyse).

== Publications dans le temps

Le graphe couvre des publications de 1984 à 2024, avec une concentration visible sur les années 2005–2023. Le pic de production se situe autour de 2015–2018 pour la plupart des équipes.

== Centralité

L'analyse de centralité sur le réseau de co-authorship donne quelques résultats intéressants. La betweenness centrality identifie les chercheurs qui font le lien entre plusieurs groupes — ce sont souvent des chercheurs avec des thématiques transversales ou qui ont bougé d'équipe.

```python
G = build_coauthor_network(g)  # nx.Graph, LRE membres seulement
betweenness = nx.betweenness_centrality(G)
top5 = sorted(betweenness.items(), key=lambda x: -x[1])[:5]
```

== Communautés vs équipes

On a utilisé l'algorithme de Louvain (via `python-louvain`) pour détecter des communautés automatiquement et les comparer aux équipes déclarées dans le graphe. Les communautés détectées correspondent assez bien aux équipes officielles, ce qui confirme que les collaborations intra-équipe sont bien plus fréquentes que les collaborations inter-équipes.

== Collaboration inter-équipes

La requête Q5 identifie 3 paires d'équipes avec des publications communes. La matrice de collaboration équipe×équipe est assez creuse, ce qui n'est pas surprenant pour un labo de cette taille.

Les figures générées sont dans `step8/figures/`.

#pagebreak()


= Step 9 — Requêtes SPARQL

Les requêtes sont dans `step9/queries.rq` et exécutées via `step9/run_queries.py` (ou depuis l'interface web via `/queries`). Voici les 8 requêtes et leurs résultats sur le graphe actuel.

== Q1 — Publications par an

```sparql
SELECT ?year (COUNT(DISTINCT ?pub) AS ?nb_publications)
WHERE {
  ?pub rdf:type lre:Publication ; lre:inYear ?y .
  BIND(STRAFTER(STR(?y), "year_") AS ?year)
}
GROUP BY ?year ORDER BY ASC(?year)
```

*40 années* représentées, de 1984 à 2024.

== Q2 — Publications par équipe

```sparql
SELECT ?team (COUNT(DISTINCT ?pub) AS ?nb_publications)
WHERE {
  ?pub rdf:type lre:Publication ; lre:authoredBy ?r .
  ?r lre:memberOf ?t .
  BIND(STRAFTER(STR(?t), "team_") AS ?team)
}
GROUP BY ?team ORDER BY DESC(?nb_publications)
```

*5 équipes* (AA, IA, TIRF, SÉCUSYS, MNSHS). Les résultats sont affichés dans la page `/queries` de l'interface.

== Q3 — Top 5 chercheurs

```sparql
SELECT ?name ?team (COUNT(DISTINCT ?pub) AS ?nb_publications)
WHERE {
  ?r rdf:type lre:Researcher ; foaf:name ?name ; lre:memberOf ?t .
  BIND(STRAFTER(STR(?t), "team_") AS ?team)
  ?pub lre:authoredBy ?r .
}
GROUP BY ?name ?team
ORDER BY DESC(?nb_publications) LIMIT 5
```

== Q4 — Hubs du réseau (co-auteurs distincts)

```sparql
SELECT ?name ?team (COUNT(DISTINCT ?co) AS ?nb_coauthors)
WHERE {
  ?r rdf:type lre:Researcher ; foaf:name ?name ;
     lre:memberOf ?t ; lre:coAuthorOf ?co .
  BIND(STRAFTER(STR(?t), "team_") AS ?team)
}
GROUP BY ?name ?team ORDER BY DESC(?nb_coauthors) LIMIT 10
```

== Q5 — Collaborations inter-équipes

```sparql
SELECT ?team1 ?team2 (COUNT(DISTINCT ?pub) AS ?shared_publications)
WHERE {
  ?pub rdf:type lre:Publication ;
       lre:authoredBy ?r1 ; lre:authoredBy ?r2 .
  ?r1 lre:memberOf ?t1 . ?r2 lre:memberOf ?t2 .
  FILTER(?t1 != ?t2 && STR(?t1) < STR(?t2))
  BIND(STRAFTER(STR(?t1), "team_") AS ?team1)
  BIND(STRAFTER(STR(?t2), "team_") AS ?team2)
}
GROUP BY ?team1 ?team2 ORDER BY DESC(?shared_publications)
```

*3 paires* identifiées.

== Q6 — Topics par équipe

Cette requête nécessite que `lre:hasTopic` soit dans le graphe — ce qui est bien le cas après la reconstruction. Elle retourne *55 lignes*, ce qui donne une vue des thématiques dominantes par équipe.

```sparql
SELECT ?team ?topic (COUNT(DISTINCT ?pub) AS ?nb_publications)
WHERE {
  ?pub rdf:type lre:Publication ;
       lre:hasTopic ?top ; lre:authoredBy ?r .
  ?r lre:memberOf ?t .
  ?top dcterms:title ?topic .
  BIND(STRAFTER(STR(?t), "team_") AS ?team)
}
GROUP BY ?team ?topic ORDER BY ?team DESC(?nb_publications)
```

== Q7 — Paires à 2 sauts sans co-authorship direct

```sparql
SELECT DISTINCT ?name1 ?team1 ?name2 ?team2
WHERE {
  ?r1 rdf:type lre:Researcher ; foaf:name ?name1 ;
      lre:memberOf ?t1 ; lre:coAuthorOf ?mid .
  ?mid lre:coAuthorOf ?r2 .
  ?r2 rdf:type lre:Researcher ; foaf:name ?name2 ; lre:memberOf ?t2 .
  FILTER(?r1 != ?r2 && STR(?r1) < STR(?r2))
  FILTER NOT EXISTS { ?r1 lre:coAuthorOf ?r2 }
  BIND(STRAFTER(STR(?t1), "team_") AS ?team1)
  BIND(STRAFTER(STR(?t2), "team_") AS ?team2)
}
ORDER BY ?team1 ?name1 LIMIT 30
```

Cette requête est la plus coûteuse à exécuter (quelques secondes) à cause du `FILTER NOT EXISTS` combiné au chemin de longueur 2. Les résultats sont intéressants : ce sont des candidats naturels pour la link prediction — des paires qui ont un intermédiaire commun mais n'ont jamais publié ensemble.

== Q8 — Venues les plus utilisées

```sparql
SELECT ?venue_title (COUNT(DISTINCT ?pub) AS ?nb_publications)
WHERE {
  ?pub rdf:type lre:Publication ;
       lre:publishedIn ?v .
  ?v dcterms:title ?venue_title .
}
GROUP BY ?venue_title ORDER BY DESC(?nb_publications) LIMIT 10
```

*10 venues*, principalement des conférences LNCS et des revues IEEE/ACM.

#pagebreak()


= Step 10 — Prédiction de liens

L'objectif de cette partie est de prédire des triples `lre:coAuthorOf` non encore présents dans le graphe, c'est-à-dire des collaborations potentielles entre chercheurs LRE qui ne se sont pas encore co-publiés.

== Approche

On utilise *PyKEEN* avec deux modèles d'embedding : *ComplEx* et *RotatE*. Plutôt qu'un split aléatoire, on fait un split temporel : les co-authorships dont la première co-publication date de *2022 ou avant* vont en train, ceux de *2023* en validation, et *après 2023* en test. C'est plus réaliste — on simule une prédiction dans le temps.

```python
Y_TRAIN = 2022  # coAuthorOf : première co-pub ≤ 2022 → train
Y_VALID = 2023  # première co-pub en 2023 → valid
               # > 2023 → test
```

Les `TriplesFactory` partagent le même vocabulaire entité→ID pour les trois splits, ce qui est nécessaire pour que les embeddings soient cohérents à l'évaluation.

== Résultats

Les deux modèles sont entraînés 200 epochs avec Adam en mode `filtered` (les triplets connus sont exclus du classement). Une grille sur `embedding_dim` ∈ {64, 128} sélectionne la meilleure configuration sur la MRR de validation.

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 7pt,
  [*Modèle*], [*dim*], [*Relation*], [*n\_test*], [*MRR*], [*H\@1*], [*H\@10*],
  [ComplEx], [128], [coAuthorOf], [1718], [0.0040], [0.0006], [0.0061],
  [ComplEx], [128], [memberOf],   [5],    [0.0013], [0.0000], [0.0000],
  [ComplEx], [128], [hasTopic],   [86],   [0.0253], [0.0058], [0.0523],
  [*RotatE*], [*128*], [*coAuthorOf*], [*1718*], [*0.0065*], [*0.0009*], [*0.0172*],
  [*RotatE*], [*128*], [*memberOf*],   [*5*],    [*0.3042*], [*0.2000*], [*0.4000*],
  [*RotatE*], [*128*], [*hasTopic*],   [*86*],   [*0.2265*], [*0.1628*], [*0.3372*],
)

Sur `coAuthorOf` — la tâche principale — les deux modèles donnent des scores modestes (MRR < 0.01), ce qui est attendu pour un graphe de cette taille où les paires de test sont rares. RotatE se distingue nettement sur `memberOf` (MRR 0.30, H\@1 0.20) et `hasTopic` (MRR 0.23, H\@10 0.34), ce qui montre que les embeddings capturent bien la structure des relations fonctionnelles et sémantiques.

Les scores bruts sont négatifs (autour de -3 à -2.8) parce que RotatE calcule le score comme l'opposé d'une distance dans l'espace d'embedding :

$ "score"(h, r, t) = -norm(h compose r - t) $

Ce qui compte, c'est le classement relatif, pas la valeur absolue.

== Top 20 collaborations prédites

Les paires ci-dessous sont les 20 co-authorships non présents dans le graphe auxquels RotatE donne les scores les plus élevés :

#table(
  columns: (auto, 1fr, 1fr, auto),
  stroke: 0.5pt + luma(180),
  fill: (col, row) => if row == 0 { rgb("#eef2ff") } else if calc.odd(row) { luma(252) } else { white },
  inset: 7pt,
  [*\#*], [*Chercheur A*], [*Chercheur B*], [*Score*],
  [1],  [Élodie Puybareau],        [Guillaume Tochon],          [-2.71],
  [2],  [Élodie Puybareau],        [Baptiste Esteban],          [-3.39],
  [3],  [Jim E. Newton],           [Florian Renkin],            [-3.50],
  [4],  [Élodie Puybareau],        [Gonzalo Romero-Garcia],     [-3.57],
  [5],  [Nicolas Boutry],          [Baptiste Esteban],          [-3.60],
  [6],  [Baptiste Esteban],        [Jonathan Fabrizio],         [-3.68],
  [7],  [Baptiste Esteban],        [Joseph Chazalon],           [-3.73],
  [8],  [Alexandre Duret-Lutz],    [Jim E. Newton],             [-3.74],
  [9],  [Edwin Carlinet],          [Alexandre Duret-Lutz],      [-3.79],
  [10], [Élodie Puybareau],        [Jimmy Randrianasoa],        [-3.85],
  [11], [Alexandre Duret-Lutz],    [Nicolas Boutry],            [-3.85],
  [12], [Joseph Chazalon],         [Alexandre Duret-Lutz],      [-3.87],
  [13], [Jimmy Randrianasoa],      [Guillaume Tochon],          [-3.88],
  [14], [David Beserra],           [Loïc Rouquette],            [-3.89],
  [15], [Jimmy Randrianasoa],      [Thierry Géraud],            [-3.89],
  [16], [Élodie Puybareau],        [Alexandre Duret-Lutz],      [-3.90],
  [17], [Thierry Géraud],          [Didier Verna],              [-3.90],
  [18], [David Beserra],           [Daniel Stan],               [-3.91],
  [19], [Adrien Pommellet],        [Riadh Robbana],             [-3.92],
  [20], [Baptiste Esteban],        [Jim E. Newton],             [-3.92],
)

Élodie Puybareau et Baptiste Esteban apparaissent souvent en tête — leurs embeddings sont proches de plusieurs clusters dans l'espace latent, ce qui suggère des positions de hub potentiel. Ces prédictions sont accessibles dans l'interface web via la route `/links`.

#note[
  *Note éthique :* ces prédictions sont des estimations statistiques basées sur la structure du graphe. Elles ne représentent pas des recommandations ni des jugements sur les chercheurs concernés.
]

#pagebreak()


= Structure du projet

```
lre-kglp/
├── data/
│   ├── raw/                   # 47 fichiers XML DBLP
│   └── ec.csv                 # liste des membres LRE
│
├── step1/
│   └── collect_data.ipynb
│
├── step4/
│   ├── dblp_parser.py
│   ├── lre_graph.py
│   ├── build_graph.py
│   └── topic_modelling/
│       ├── topic_extractor.py      # modèle BERT OpenAlex
│       ├── precompute_topics.py    # pré-calcul des topics
│       └── data/
│           ├── precomputed_topics.json
│           └── openalex_taxonomy.json
│
├── step5/
│   └── lre_onto.ttl           # classes + propriétés
│
├── step6/
│   └── lre_onto.ttl           # + axiomes RDFS/OWL
│
├── step7/
│   ├── app.py                 # Flask (6 vues)
│   └── export_full.py
│
├── step8/
│   └── trends.py              # analyse networkx + figures
│
├── step9/
│   ├── queries.rq             # 8 requêtes SPARQL
│   └── run_queries.py
│
├── step10/
│   ├── link_prediction.py     # ComplEx + RotatE
│   ├── metrics.txt            # résultats d'évaluation
│   └── predictions.json       # top 20 collaborations prédites
│
└── output/
    ├── lre_kg.ttl             # graphe sérialisé (18 475 triplets)
    ├── lre_kg.html            # visualisation co-authorship
    └── lre_kg_full.html       # visualisation complète
```

== Lancer le projet

```bash
# 1. Créer le venv et installer les dépendances
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Construire le graphe
python step4/build_graph.py          # → output/lre_kg.ttl

# 3. Analyse de réseau
python step8/trends.py               # → step8/figures/*.png

# 4. Requêtes SPARQL
python step9/run_queries.py          # → step9/results/*.csv

# 5. Prédiction de liens
python step10/link_prediction.py     # → step10/metrics.txt, predictions.json

# 6. Interface web
python step7/app.py                  # → http://localhost:5050
```

#pagebreak()


= Bilan

Le pipeline de construction tourne de bout en bout sans intervention manuelle : collecte DBLP, parsing XML, graphe RDF, topics OpenAlex precomputed, visualisation Flask et link prediction PyKEEN. Le split temporel leak-free est plus réaliste qu'un split aléatoire — on ne prédit que des liens qui ne pouvaient pas avoir été vus à l'entraînement.

Les métriques de link prediction sur `coAuthorOf` restent faibles (MRR ≈ 0.006 pour RotatE), ce qui est attendu : le graphe LRE est petit (47 chercheurs), le nombre de paires de test est limité, et la tâche est intrinsèquement bruitée — il n'y a pas de raison que deux chercheurs du même cluster qui ne se sont jamais co-publiés finissent effectivement par collaborer dans la fenêtre de test. Sur les autres relations (`memberOf`, `hasTopic`), les scores sont nettement meilleurs, ce qui suggère que les embeddings capturent bien la structure du graphe pour les relations plus déterministes.

La classification des topics par BERT OpenAlex donne des subfields cohérents (Combinatorics, Computer Vision, Cryptography…) mais reste tributaire du titre seul — sans abstract, certaines publications transversales sont mal classifiées. L'utilisation de `precomputed_topics.json` évite de re-tourner le modèle à chaque reconstruction.

Les données DBLP sont publiques et professionnelles. Les prédictions de liens sont des estimations statistiques sur la structure du graphe ; elles ne valent pas recommandation de collaboration et ne reflètent pas les préférences des chercheurs concernés.
