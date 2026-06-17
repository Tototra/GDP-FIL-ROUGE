from collections import defaultdict
from rdflib import Namespace
import numpy as np

LRE = Namespace("http://lre.epita.fr/kg/")
SEED = 42

Y_TRAIN = 2022
Y_VALID = 2023


def extract_year(uri):
    if "year_" not in uri:
        return None
    try:
        return int(uri.split("year_")[-1])
    except ValueError:
        return None


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
