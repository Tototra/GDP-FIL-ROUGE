import re
import csv
from pathlib import Path

from rdflib import Graph
from rdflib.query import Result

ROOT = Path(__file__).parent.parent
TTL_PATH = ROOT / "output" / "lre_kg.ttl"
QUERIES_FILE = Path(__file__).parent / "queries.rq"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

PREFIXES = """
PREFIX lre:     <http://lre.epita.fr/kg/>
PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl:     <http://www.w3.org/2002/07/owl#>
"""


def split_queries(text: str) -> list[tuple[str, str]]:
    queries = []
    pattern = re.compile(r"#\s*(Q\d+[^\n]*)\n(.*?)(?=\n#\s*Q\d+|\Z)", re.DOTALL)
    for m in pattern.finditer(text):
        name = re.sub(r"[^A-Za-z0-9_\-]", "_", m.group(1).strip())[:60]
        body = m.group(2).strip()
        body = re.sub(r"^PREFIX\s+\S+\s+<[^>]+>\s*", "", body, flags=re.MULTILINE).strip()
        if "SELECT" in body.upper():
            queries.append((name, PREFIXES + body))
    return queries


def run_query(g: Graph, sparql: str) -> Result:
    return g.query(sparql)


def save_result(name: str, result: Result) -> None:
    rows = list(result)
    if not rows:
        print(f"  {name}: 0 rows")
        return

    headers = [str(v) for v in result.vars]
    path = RESULTS_DIR / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([str(v) if v is not None else "" for v in row])

    print(f"  {name}: {len(rows)} rows → {path.name}")
    for row in rows[:5]:
        print("    " + " | ".join(str(v) for v in row))
    if len(rows) > 5:
        print(f"    … ({len(rows) - 5} more)")


def main() -> None:
    print("Loading graph …")
    g = Graph()
    g.parse(str(TTL_PATH))
    print(f"  {len(g)} triples loaded\n")

    raw = QUERIES_FILE.read_text(encoding="utf-8")
    queries = split_queries(raw)
    print(f"Found {len(queries)} queries in {QUERIES_FILE.name}\n")

    for name, sparql in queries:
        print(f"Running {name} …")
        try:
            result = run_query(g, sparql)
            save_result(name, result)
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    print(f"All results saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
