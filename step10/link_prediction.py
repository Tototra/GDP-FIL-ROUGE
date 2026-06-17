import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import FOAF, DCTERMS

# Pykeen Imports
from pykeen.triples import TriplesFactory
from pykeen.evaluation import RankBasedEvaluator
from pykeen.pipeline import pipeline

ROOT = Path(__file__).parent.parent
TTL_PATH = ROOT / "output" / "lre_kg.ttl"
OUT = Path(__file__).parent

LRE = Namespace("http://lre.epita.fr/kg/")

Y_TRAIN = 2022
Y_VALID = 2023
NUM_EPOCHS = 200
EMB_DIMS = [64, 128]
MODEL_LR = {"ComplEx": 1e-2, "RotatE": 1e-3}
TOPK = 20
SEED = 42

TARGET_RELATIONS = ["coAuthorOf", "memberOf", "hasTopic"]


def extract_year(uri):
    if "year_" not in uri:
        return None
    try:
        return int(uri.split("year_")[-1])
    except ValueError:
        return None


def load_graph():
    if not TTL_PATH.exists():
        sys.exit(f"Graph not found: {TTL_PATH}\nRun python step4/build_graph.py first.")
    graph = Graph()
    graph.parse(str(TTL_PATH))
    print(f"Graph loaded: {len(graph)} triples")
    return graph


def get_publication_years(graph):
    years = {}
    for pub, year_node in graph.subject_objects(LRE.inYear):
        year_num = extract_year(str(year_node))
        if year_num is not None:
            years[pub] = year_num
    return years


def get_publication_authors(graph):
    authors = defaultdict(set)
    for pub, author in graph.subject_objects(LRE.authoredBy):
        authors[pub].add(author)
    return authors


def get_first_coauthor_years(pub_years, pub_authors):
    first_coauthor_years = {}
    for pub, author_set in pub_authors.items():
        if pub not in pub_years:
            continue
        year = pub_years[pub]
        sorted_authors = sorted(author_set, key=str)
        for i in range(len(sorted_authors)):
            for j in range(i + 1, len(sorted_authors)):
                key = frozenset((sorted_authors[i], sorted_authors[j]))
                if key not in first_coauthor_years or year < first_coauthor_years[key]:
                    first_coauthor_years[key] = year
    return first_coauthor_years


def build_split(graph):
    rng = np.random.default_rng(SEED)
    pub_years = get_publication_years(graph)
    pub_authors = get_publication_authors(graph)
    coauthor_pairs = get_first_coauthor_years(pub_years, pub_authors)

    train, valid, test = [], [], []

    for pair, year in coauthor_pairs.items():
        author1, author2 = sorted((str(x) for x in pair))
        coauthor_edges = [
            (author1, str(LRE.coAuthorOf), author2),
            (author2, str(LRE.coAuthorOf), author1),
        ]
        if year <= Y_TRAIN:
            train += coauthor_edges
        elif year <= Y_VALID:
            valid += coauthor_edges
        else:
            test += coauthor_edges

    past_topics = []
    for pub, yr in pub_years.items():
        if yr > Y_TRAIN:
            continue
        for rel in (LRE.authoredBy, LRE.publishedIn, LRE.inYear):
            for o in graph.objects(pub, rel):
                train.append((str(pub), str(rel), str(o)))
        for o in graph.objects(pub, LRE.hasTopic):
            past_topics.append((str(pub), str(LRE.hasTopic), str(o)))

    def split_random(rows):
        rows = list(rows)
        rng.shuffle(rows)
        n = len(rows)
        return (
            rows[: int(0.8 * n)],
            rows[int(0.8 * n) : int(0.9 * n)],
            rows[int(0.9 * n) :],
        )

    team_memberships = [
        (str(s), str(LRE.memberOf), str(o))
        for s, o in graph.subject_objects(LRE.memberOf)
    ]
    members_train, members_valid, members_test = split_random(team_memberships)
    topics_train, topics_valid, topics_test = split_random(past_topics)
    train += members_train + topics_train
    valid += members_valid + topics_valid
    test += members_test + topics_test

    def remove_duplicates(rows):
        seen, out = set(), []
        for r in rows:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    train = remove_duplicates(train)
    train_set = set(train)
    valid = [r for r in remove_duplicates(valid) if r not in train_set]
    valid_set = set(valid)
    test = [
        r for r in remove_duplicates(test) if r not in train_set and r not in valid_set
    ]
    return train, valid, test, coauthor_pairs


def create_triples_factories(train, valid, test):
    base = TriplesFactory.from_labeled_triples(
        np.array(train + valid + test, dtype=str)
    )

    def sub_factory(rows):
        return TriplesFactory.from_labeled_triples(
            np.array(rows, dtype=str),
            entity_to_id=base.entity_to_id,
            relation_to_id=base.relation_to_id,
        )

    return (
        sub_factory(train),
        sub_factory(valid),
        sub_factory(test),
    )


def evaluate_mrr(model, eval_tf, filter_tfs):
    evaluator = RankBasedEvaluator(filtered=True)
    res = evaluator.evaluate(
        model=model,
        mapped_triples=eval_tf.mapped_triples,
        additional_filter_triples=[tf.mapped_triples for tf in filter_tfs],
    )
    return float(res.get_metric("both.realistic.inverse_harmonic_mean_rank"))


def train_and_tune(model_name, train_tf, valid_tf, test_tf):
    learning_rate = MODEL_LR.get(model_name, 1e-3)
    best_config = None
    attempts = []
    for dim in EMB_DIMS:
        result = pipeline(
            training=train_tf,
            validation=valid_tf,
            testing=test_tf,
            model=model_name,
            model_kwargs=dict(embedding_dim=dim),
            training_kwargs=dict(num_epochs=NUM_EPOCHS, batch_size=256),
            optimizer="Adam",
            optimizer_kwargs=dict(lr=learning_rate),
            evaluator_kwargs=dict(filtered=True),
            random_seed=SEED,
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
        val_mrr = evaluate_mrr(result.model, valid_tf, [train_tf])
        print(f"    {model_name} dim={dim:<4} lr={learning_rate} val MRR={val_mrr:.4f}")
        attempts.append(
            dict(dim=dim, lr=learning_rate, epochs=NUM_EPOCHS, val_mrr=val_mrr)
        )
        if best_config is None or val_mrr > best_config["val_mrr"]:
            best_config = dict(
                model_name=model_name, dim=dim, val_mrr=val_mrr, result=result
            )
    best_config["attempts"] = attempts
    return best_config


def get_per_relation_metrics(model, train_tf, valid_tf, test_tf):
    metrics_table = []
    relation_to_id = test_tf.relation_to_id
    test_triples = test_tf.mapped_triples

    for rel_name in TARGET_RELATIONS:
        rel_id = relation_to_id.get(str(LRE[rel_name]))
        if rel_id is None:
            continue

        relation_mask = test_triples[:, 1] == rel_id
        if int(relation_mask.sum()) == 0:
            continue

        evaluator = RankBasedEvaluator(filtered=True)
        results = evaluator.evaluate(
            model=model,
            mapped_triples=test_triples[relation_mask],
            additional_filter_triples=[
                train_tf.mapped_triples,
                valid_tf.mapped_triples,
                test_tf.mapped_triples,
            ],
        )
        metrics_table.append(
            dict(
                relation=rel_name,
                n_test=int(relation_mask.sum()),
                MRR=float(
                    results.get_metric("both.realistic.inverse_harmonic_mean_rank")
                ),
                H1=float(results.get_metric("both.realistic.hits_at_1")),
                H3=float(results.get_metric("both.realistic.hits_at_3")),
                H10=float(results.get_metric("both.realistic.hits_at_10")),
            )
        )
    return metrics_table


def get_display_name(graph, uri):
    uri_ref = URIRef(uri)
    for prop in (FOAF.name, DCTERMS.title):
        value = graph.value(uri_ref, prop)
        if value:
            return str(value)

    for token in ("team_", "topic_", "person_", "pub_"):
        if token in uri:
            return uri.split(token)[-1]

    return uri.rsplit("/", 1)[-1]


def get_top_predictions(
    model, tf, graph, relation, heads, tails, k=TOPK, symmetric=False
):
    rel_id = tf.relation_to_id.get(str(LRE[relation]))
    if rel_id is None:
        return []

    entity_to_id = tf.entity_to_id
    valid_heads = [h for h in heads if h in entity_to_id]
    valid_tails = [t for t in tails if t in entity_to_id]

    if not valid_heads or not valid_tails:
        return []

    existing_edges = set()
    for s, o in graph.subject_objects(LRE[relation]):
        existing_edges.add((str(s), str(o)))

    model.eval()
    scored_triples = []

    with torch.no_grad():
        for h in valid_heads:
            head_id = entity_to_id[h]
            tail_tensors = torch.tensor(
                [entity_to_id[t] for t in valid_tails], dtype=torch.long
            )

            repeated_heads = torch.full((len(valid_tails),), head_id, dtype=torch.long)
            repeated_relations = torch.full(
                (len(valid_tails),), rel_id, dtype=torch.long
            )

            combinations = torch.stack(
                [repeated_heads, repeated_relations, tail_tensors], 1
            )
            scores = model.score_hrt(combinations).view(-1).tolist()

            for t, score in zip(valid_tails, scores):
                if h == t or (h, t) in existing_edges:
                    continue
                if symmetric and (t, h) in existing_edges:
                    continue
                scored_triples.append((score, h, t))

    scored_triples.sort(reverse=True)
    final_predictions, seen_pairs = [], set()

    for score, h, t in scored_triples:
        pair_id = frozenset((h, t)) if symmetric else (h, t)
        if pair_id in seen_pairs:
            continue
        seen_pairs.add(pair_id)
        final_predictions.append((score, h, t))
        if len(final_predictions) >= k:
            break

    return final_predictions


def save_metrics_report(model_runs, train_tf, valid_tf, test_tf):

    report_lines = [
        f"Link Prediction Report",
        f"Configuration: (train <= {Y_TRAIN}, valid {Y_VALID}, test > {Y_VALID})",
        "",
    ]

    for run in model_runs:
        model = run["result"].model
        model_name = run["model_name"]
        dim = run["dim"]
        test_mrr = evaluate_mrr(model, test_tf, [train_tf, valid_tf])

        report_lines.append(
            f"## {model_name} (Best dim={dim}, Val MRR={run['val_mrr']:.4f})"
        )
        report_lines.append(
            "Tuning history: "
            + " | ".join(
                f"dim={t['dim']}, lr={t['lr']} -> valMRR={t['val_mrr']:.4f}"
                for t in run["attempts"]
            )
        )
        report_lines.append(
            f"{'relation':<12}{'n_test':>8}{'MRR':>9}{'H@1':>8}{'H@3':>8}{'H@10':>8}"
        )
        report_lines.append("-" * 53)
        report_lines.append(
            f"{'ALL':<12}{test_tf.num_triples:>8}{test_mrr:>9.4f}{'':>8}{'':>8}{'':>8}"
        )

        for metric in get_per_relation_metrics(model, train_tf, valid_tf, test_tf):
            report_lines.append(
                f"{metric['relation']:<12}{metric['n_test']:>8}{metric['MRR']:>9.4f}"
                f"{metric['H1']:>8.4f}{metric['H3']:>8.4f}{metric['H10']:>8.4f}"
            )
        report_lines.append("")

    with open(OUT / "metrics.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")


def export_predictions(
    model, tf, graph, relation, heads, tails, filename, keys, name, symmetric=False
):
    predictions = get_top_predictions(
        model, tf, graph, relation, heads, tails, symmetric=symmetric
    )

    formatted_data = []
    for score, h, t in predictions:
        record = {
            keys[0]: get_display_name(graph, h),
            keys[1]: get_display_name(graph, t),
            "score": round(score, 4),
            "model": name,
        }
        formatted_data.append(record)

    with open(OUT / filename, "w", encoding="utf-8") as f:
        json.dump(formatted_data, f, ensure_ascii=False, indent=2)

    print(f"- Top {len(formatted_data)} {relation} -> {filename}")


def main():
    graph = load_graph()
    print(
        f"\nLeak-free temporal split (train <= {Y_TRAIN}, valid = {Y_VALID}, test > {Y_VALID}) ..."
    )
    train, valid, test, coauthor_pairs = build_split(graph)

    def count_relations(triples_list):
        counter = defaultdict(int)
        for _, rel, _ in triples_list:
            counter[rel.split("kg/")[-1]] += 1
        return dict(sorted(counter.items()))

    print(f"  train={len(train)} {count_relations(train)}")
    print(f"  valid={len(valid)} {count_relations(valid)}")
    print(f"  test ={len(test)} {count_relations(test)}")

    if len([1 for _, rel, _ in test if rel.endswith("coAuthorOf")]) == 0:
        sys.exit("No coAuthorOf edges in test set. Adjust temporal variables.")

    train_tf, valid_tf, test_tf = create_triples_factories(train, valid, test)
    print(
        f"  Entities = {train_tf.num_entities} | Relations = {train_tf.num_relations}"
    )

    model_runs = []
    for name in ("ComplEx", "RotatE"):
        print(f"\n=== Running model: {name} ===")
        model_runs.append(train_and_tune(name, train_tf, valid_tf, test_tf))

    save_metrics_report(model_runs, train_tf, valid_tf, test_tf)

    best_run = max(model_runs, key=lambda r: r["val_mrr"])
    best_model = best_run["result"].model
    best_model_name = best_run["model_name"]

    researchers = [str(sub) for sub in graph.subjects(LRE.memberOf, None)]
    teams = [str(sub) for sub in graph.subjects(RDF.type, LRE.Team)]
    topics = [str(sub) for sub in graph.subjects(RDF.type, LRE.Topic)]
    publications = [str(sub) for sub in graph.subjects(RDF.type, LRE.Publication)]

    export_predictions(
        best_model,
        train_tf,
        graph,
        "coAuthorOf",
        researchers,
        researchers,
        "predictions.json",
        ["name_a", "name_b"],
        best_model_name,
        symmetric=True,
    )
    export_predictions(
        best_model,
        train_tf,
        graph,
        "memberOf",
        researchers,
        teams,
        "predictions_memberOf.json",
        ["researcher", "team"],
        best_model_name,
    )
    export_predictions(
        best_model,
        train_tf,
        graph,
        "hasTopic",
        publications,
        topics,
        "predictions_hasTopic.json",
        ["publication", "topic"],
        best_model_name,
    )


if __name__ == "__main__":
    main()
