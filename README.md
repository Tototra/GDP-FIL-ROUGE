# LRE Knowledge Graph & Link Prediction

**Équipe :** Yako Lemeilleur, Thomas Trahant — EPITA MGD 2025–2026

Graphe de connaissances RDF sur les publications des chercheurs du LRE (EPITA), construit à partir des données DBLP. Ontologie OWL, requêtes SPARQL, analyse de réseau networkx et prédiction de liens avec PyKEEN.

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Reproduire les résultats

### 1 — Construire le graphe

```bash
python step4/build_graph.py
# → output/lre_kg.ttl (~18 475 triplets)
```

### 2 — Générer les figures

```bash
python step8/trends.py
# → step8/figures/*.png (7 figures)
```

### 3 — Requêtes SPARQL

```bash
python step9/run_queries.py
# → step9/results/Q*.csv (8 fichiers)
```

### 4 — Link prediction

```bash
python step10/link_prediction.py
# → step10/metrics.txt, step10/predictions.json
```

### 5 — Interface web

```bash
python step7/app.py
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
