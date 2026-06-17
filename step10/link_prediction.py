
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import FOAF, DCTERMS

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


def _year(uri: str):
    if "year_" not in uri:
        return None
    try:
        return int(uri.split("year_")[-1])
    except ValueError:
        return None


def load_graph() -> Graph:
    if not TTL_PATH.exists():
        sys.exit(f"Graph not found: {TTL_PATH}\nRun python step4/build_graph.py first.")
    g = Graph()
    g.parse(str(TTL_PATH))
    print(f"Graph loaded: {len(g)} triples")
    return g


def publication_years(g: Graph) -> dict:
    years = {}
    for pub, _, y in g.triples((None, LRE.inYear, None)):
        yr = _year(str(y))
        if yr is not None:
            years[pub] = yr
    return years


def publication_authors(g: Graph) -> dict:
    authors = defaultdict(set)
    for pub, _, a in g.triples((None, LRE.authoredBy, None)):
        authors[pub].add(a)
    return authors


def first_coauthor_year(pub_years, pub_authors) -> dict:
    first = {}
    for pub, authors in pub_authors.items():
        if pub not in pub_years:
            continue
        yr = pub_years[pub]
        al = sorted(authors, key=str)
        for i in range(len(al)):
            for j in range(i + 1, len(al)):
                key = frozenset((al[i], al[j]))
                if key not in first or yr < first[key]:
                    first[key] = yr
    return first


def build_split(g: Graph):
    rng = np.random.default_rng(SEED)
    pub_years = publication_years(g)
    pub_authors = publication_authors(g)
    pair_year = first_coauthor_year(pub_years, pub_authors)

    train, valid, test = [], [], []

    for pair, yr in pair_year.items():
        a, b = sorted((str(x) for x in pair))
        edges = [(a, str(LRE.coAuthorOf), b), (b, str(LRE.coAuthorOf), a)]
        if yr <= Y_TRAIN:
            train += edges
        elif yr <= Y_VALID:
            valid += edges
        else:
            test += edges

    past_hastopic = []
    for pub, yr in pub_years.items():
        if yr > Y_TRAIN:
            continue                   
        for rel in (LRE.authoredBy, LRE.publishedIn, LRE.inYear):
            for _, _, o in g.triples((pub, rel, None)):
                train.append((str(pub), str(rel), str(o)))
        for _, _, o in g.triples((pub, LRE.hasTopic, None)):
            past_hastopic.append((str(pub), str(LRE.hasTopic), str(o)))

    def split_random(rows):
        rows = list(rows)
        rng.shuffle(rows)
        n = len(rows)
        return rows[: int(.8 * n)], rows[int(.8 * n): int(.9 * n)], rows[int(.9 * n):]

    member = [(str(s), str(LRE.memberOf), str(o))
              for s, _, o in g.triples((None, LRE.memberOf, None))]
    m_tr, m_va, m_te = split_random(member)
    h_tr, h_va, h_te = split_random(past_hastopic)
    train += m_tr + h_tr
    valid += m_va + h_va
    test += m_te + h_te

    def dedup(rows):
        seen, out = set(), []
        for r in rows:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    train = dedup(train)
    tr_set = set(train)
    valid = [r for r in dedup(valid) if r not in tr_set]
    va_set = set(valid)
    test = [r for r in dedup(test) if r not in tr_set and r not in va_set]
    return train, valid, test, pair_year


def make_factories(train, valid, test):
    from pykeen.triples import TriplesFactory
    base = TriplesFactory.from_labeled_triples(
        np.array(train + valid + test, dtype=str))

    def sub(rows):
        return TriplesFactory.from_labeled_triples(
            np.array(rows, dtype=str),
            entity_to_id=base.entity_to_id,
            relation_to_id=base.relation_to_id,
        )
    return sub(train), sub(valid), sub(test)


def evaluate_mrr(model, eval_tf, filter_tfs) -> float:
    from pykeen.evaluation import RankBasedEvaluator
    ev = RankBasedEvaluator(filtered=True)
    res = ev.evaluate(
        model=model,
        mapped_triples=eval_tf.mapped_triples,
        additional_filter_triples=[tf.mapped_triples for tf in filter_tfs],
    )
    return float(res.get_metric("both.realistic.inverse_harmonic_mean_rank"))


def train_tuned(model_name, train_tf, valid_tf, test_tf):
    from pykeen.pipeline import pipeline
    lr = MODEL_LR.get(model_name, 1e-3)
    best = None
    attempts = []
    for dim in EMB_DIMS:
        result = pipeline(
            training=train_tf, validation=valid_tf, testing=test_tf,
            model=model_name, model_kwargs=dict(embedding_dim=dim),
            training_kwargs=dict(num_epochs=NUM_EPOCHS, batch_size=256),
            optimizer="Adam", optimizer_kwargs=dict(lr=lr),
            evaluator_kwargs=dict(filtered=True),
            random_seed=SEED, device="cuda" if torch.cuda.is_available() else "cpu",
        )
        val_mrr = evaluate_mrr(result.model, valid_tf, [train_tf])
        print(f"    {model_name} dim={dim:<4} lr={lr} val MRR={val_mrr:.4f}")
        attempts.append(dict(dim=dim, lr=lr, epochs=NUM_EPOCHS, val_mrr=val_mrr))
        if best is None or val_mrr > best["val_mrr"]:
            best = dict(model_name=model_name, dim=dim, val_mrr=val_mrr, result=result)
    best["attempts"] = attempts
    return best


def per_relation_metrics(model, train_tf, valid_tf, test_tf):
    from pykeen.evaluation import RankBasedEvaluator
    rows = []
    rel_to_id = test_tf.relation_to_id
    mapped = test_tf.mapped_triples
    for rel in TARGET_RELATIONS:
        rid = rel_to_id.get(str(LRE[rel]))
        if rid is None:
            continue
        mask = mapped[:, 1] == rid
        if int(mask.sum()) == 0:
            continue
        ev = RankBasedEvaluator(filtered=True)
        res = ev.evaluate(
            model=model, mapped_triples=mapped[mask],
            additional_filter_triples=[train_tf.mapped_triples,
                                       valid_tf.mapped_triples,
                                       test_tf.mapped_triples],
        )
        rows.append(dict(
            relation=rel, n_test=int(mask.sum()),
            MRR=float(res.get_metric("both.realistic.inverse_harmonic_mean_rank")),
            H1=float(res.get_metric("both.realistic.hits_at_1")),
            H3=float(res.get_metric("both.realistic.hits_at_3")),
            H10=float(res.get_metric("both.realistic.hits_at_10")),
        ))
    return rows


def label_name(g, uri):
    ref = URIRef(uri)
    for p in (FOAF.name, DCTERMS.title):
        v = g.value(ref, p)
        if v:
            return str(v)
    for token in ("team_", "topic_", "person_", "pub_"):
        if token in uri:
            return uri.split(token)[-1]
    return uri.rsplit("/", 1)[-1]


def top_predictions(model, tf, g, relation, heads, tails, k=TOPK, symmetric=False):
    rid = tf.relation_to_id.get(str(LRE[relation]))
    if rid is None:
        return []
    e2id = tf.entity_to_id
    heads = [h for h in heads if h in e2id]
    tails = [t for t in tails if t in e2id]
    if not heads or not tails:
        return []

    existing = set()
    for s, _, o in g.triples((None, LRE[relation], None)):
        existing.add((str(s), str(o)))

    model.eval()
    scored = []
    with torch.no_grad():
        for h in heads:
            hid = e2id[h]
            tid = torch.tensor([e2id[t] for t in tails], dtype=torch.long)
            hh = torch.full((len(tails),), hid, dtype=torch.long)
            rr = torch.full((len(tails),), rid, dtype=torch.long)
            sc = model.score_hrt(torch.stack([hh, rr, tid], 1)).view(-1).tolist()
            for t, s in zip(tails, sc):
                if h == t or (h, t) in existing:
                    continue
                if symmetric and (t, h) in existing:
                    continue
                scored.append((s, h, t))

    scored.sort(reverse=True)
    out, seen = [], set()
    for s, h, t in scored:
        key = frozenset((h, t)) if symmetric else (h, t)
        if key in seen:
            continue
        seen.add(key)
        out.append((s, h, t))
        if len(out) >= k:
            break
    return out


def main():
    try:
        import pykeen 
    except ImportError:
        sys.exit("PyKEEN non installé. Installe avec: pip install pykeen torch")

    g = load_graph()
    print(f"\nSplit temporel leak-free (train ≤ {Y_TRAIN}, valid = {Y_VALID}, "
          f"test > {Y_VALID}) …")
    train, valid, test, pair_year = build_split(g)

    def rel_counts(rows):
        c = defaultdict(int)
        for _, r, _ in rows:
            c[r.split("kg/")[-1]] += 1
        return dict(sorted(c.items()))

    print(f"  train={len(train)} {rel_counts(train)}")
    print(f"  valid={len(valid)} {rel_counts(valid)}")
    print(f"  test ={len(test)} {rel_counts(test)}")
    if len([1 for _, r, _ in test if r.endswith("coAuthorOf")]) == 0:
        sys.exit("Aucune arête coAuthorOf de test : ajuste Y_TRAIN/Y_VALID ou "
                 "régénère un graphe dense.")

    train_tf, valid_tf, test_tf = make_factories(train, valid, test)
    print(f"  entités={train_tf.num_entities}  relations={train_tf.num_relations}")

    runs = []
    for name in ("ComplEx", "RotatE"):
        print(f"\n=== {name} ===")
        runs.append(train_tuned(name, train_tf, valid_tf, test_tf))

    report = [f"Link prediction — split temporel leak-free "
              f"(train ≤ {Y_TRAIN}, valid {Y_VALID}, test > {Y_VALID})", ""]
    for run in runs:
        model, name, dim = run["result"].model, run["model_name"], run["dim"]
        g_mrr = evaluate_mrr(model, test_tf, [train_tf, valid_tf])
        report.append(f"## {name}  (best embedding_dim={dim}, val MRR={run['val_mrr']:.4f})")
        report.append("réglages essayés: " + " | ".join(
            f"dim={a['dim']},lr={a['lr']},epochs={a['epochs']} -> valMRR={a['val_mrr']:.4f}"
            for a in run["attempts"]))
        report.append(f"{'relation':<12}{'n_test':>8}{'MRR':>9}{'H@1':>8}{'H@3':>8}{'H@10':>8}")
        report.append("-" * 53)
        report.append(f"{'ALL':<12}{test_tf.num_triples:>8}{g_mrr:>9.4f}"
                      f"{'':>8}{'':>8}{'':>8}")
        for r in per_relation_metrics(model, train_tf, valid_tf, test_tf):
            report.append(f"{r['relation']:<12}{r['n_test']:>8}{r['MRR']:>9.4f}"
                          f"{r['H1']:>8.4f}{r['H3']:>8.4f}{r['H10']:>8.4f}")
        report.append("")

    report.append("Note: graphe LRE petit -> métriques modestes et bruitées "
                   "d'un run à l'autre (attendu). Le split est leak-free : les "
                   "publications postérieures à Y_TRAIN sont entièrement exclues "
                   "du train.")
    (OUT / "metrics.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n" + "\n".join(report))
    print(f"\nMétriques -> {OUT/'metrics.txt'}")

    best = max(runs, key=lambda r: r["val_mrr"])
    model, mname = best["result"].model, best["model_name"]

    members = [str(s) for s in g.subjects(LRE.memberOf, None)]
    teams = [str(o) for o in set(g.objects(None, LRE.memberOf))]
    topics = [str(s) for s in g.subjects(RDF.type, LRE.Topic)]
    pubs = [str(s) for s in g.subjects(RDF.type, LRE.Publication)]

    co = top_predictions(model, train_tf, g, "coAuthorOf", members, members,
                         symmetric=True)
    pred_co = [dict(name_a=label_name(g, h), name_b=label_name(g, t),
                    score=round(s, 4), model=mname) for s, h, t in co]
    (OUT / "predictions.json").write_text(
        json.dumps(pred_co, ensure_ascii=False, indent=2), encoding="utf-8")

    mo = top_predictions(model, train_tf, g, "memberOf", members, teams)
    pred_mo = [dict(researcher=label_name(g, h), team=label_name(g, t),
                    score=round(s, 4), model=mname) for s, h, t in mo]
    (OUT / "predictions_memberOf.json").write_text(
        json.dumps(pred_mo, ensure_ascii=False, indent=2), encoding="utf-8")

    ht = top_predictions(model, train_tf, g, "hasTopic", pubs, topics)
    pred_ht = [dict(publication=label_name(g, h), topic=label_name(g, t),
                    score=round(s, 4), model=mname) for s, h, t in ht]
    (OUT / "predictions_hasTopic.json").write_text(
        json.dumps(pred_ht, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTop {len(pred_co)} coAuthorOf  -> predictions.json (modèle {mname})")
    print(f"Top {len(pred_mo)} memberOf    -> predictions_memberOf.json")
    print(f"Top {len(pred_ht)} hasTopic    -> predictions_hasTopic.json")
    print("\nNote éthique : les liens prédits sont des estimations statistiques "
          "sur la structure du graphe, pas des recommandations sur les collègues.")


if __name__ == "__main__":
    main()
