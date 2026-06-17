import ast

import pandas as pd

from dblp_parser import parse_xml
from lre_graph import LREGraph


def build():
    graph = LREGraph()

    try:
        authors = pd.read_csv("data/ec.csv", )
    except FileNotFoundError:
        authors = pd.read_csv("data/2026_05_LRE_EC.csv", sep=";")

    for _, row in authors.iterrows():
        name = row.get("full_name")
        team = row.get("team")
        arrival = row.get("arrival_year", row.get("Année d'arrivée", 2020))

        if "dblp_pids" not in row or not pd.notna(row["dblp_pids"]):
            continue

        pid = ast.literal_eval(row["dblp_pids"])[0]
        if not pid or str(pid) == "None":
            continue

        graph.add_researcher(pid, name, team, arrival)

        try:
            publications = parse_xml(str(pid).replace("/", "_"))
            for author, coauthors, title, topic, venue, year, url in publications:
                graph.add_publication(pid, author, coauthors, title, topic, venue, year, url=url)
        except Exception as e:
            print(f"Données manquantes ignorées pour {name} ({pid}): {e}")

    graph.g.serialize("output/lre_kg.ttl", format="turtle")
    print(f"Graphe sérialisé : {len(graph.g)} triplets → output/lre_kg.ttl")


if __name__ == "__main__":
    build()
