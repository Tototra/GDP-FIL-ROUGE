from collections import defaultdict

import numpy as np
from rdflib import Graph, Namespace

LRE = Namespace("http://lre.epita.fr/kg/")


def _year(uri: str):
    if "year_" not in uri:
        return None
    try:
        return int(uri.split("year_")[-1])
    except ValueError:
        return None


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


def build_split(g: Graph, y_train: int, y_valid: int, seed: int):
    rng = np.random.default_rng(seed)
    pub_years = publication_years(g)
    pub_authors = publication_authors(g)
    pair_year = first_coauthor_year(pub_years, pub_authors)

    train, valid, test = [], [], []

    for pair, yr in pair_year.items():
        a, b = sorted((str(x) for x in pair))
        edges = [(a, str(LRE.coAuthorOf), b), (b, str(LRE.coAuthorOf), a)]
        if yr <= y_train:
            train += edges
        elif yr <= y_valid:
            valid += edges
        else:
            test += edges

    past_hastopic = []
    for pub, yr in pub_years.items():
        if yr > y_train:
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
