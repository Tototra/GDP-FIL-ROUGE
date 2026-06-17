# LRE Knowledge Graph & Link Prediction

**Équipe :** Yako Lemeilleur, Thomas Trahant, Tristan Faure, Felix Muhlke, Eliot Mercier-Del-Forno — EPITA MGD 2025–2026

Graphe de connaissances RDF sur les publications des chercheurs du LRE (EPITA), construit à partir des données DBLP. Ontologie OWL, requêtes SPARQL, analyse de réseau networkx et prédiction de liens avec PyKEEN.

## Installation

```bash
python3.11 -m venv .venv
source ./.venv/bin/activate
uv pip install -r requirements.txt
```

## Reproduire les résultats

### 1 — Construire le graphe

```bash
python3 step4/build_graph.py
```

### 2 — Générer les figures

```bash
python3 step8/trends.py
```

### 3 — Requêtes SPARQL

```bash
python3 step9/run_queries.py
```

### 4 — Link prediction

```bash
python3 step10/link_prediction.py
```

### 5 — Interface web

```bash
python3 step7/app.py
# → http://localhost:5050
```

## Structure

```
lre-kglp/
├── data/
│   ├── raw/                       
│   └── ec.csv                     
├── step4/                         
├── step5/lre_onto.ttl              
├── step6/lre_onto.ttl           
├── step7/app.py                  
├── step8/trends.py                 
├── step9/                         
├── step10/link_prediction.py     
└── output/lre_kg.ttl         
```
