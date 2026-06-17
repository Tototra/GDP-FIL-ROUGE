import requests
import json
import os

from transformers import pipeline

taxonomy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "openalex_taxonomy.json")

taxonomy_map = None
with open(taxonomy_path, "r", encoding="utf-8") as f:
    taxonomy_map = json.load(f)


class TopicExtractor:
    def __init__(self):
        self.classifier = pipeline(
            "text-classification", 
            model="OpenAlex/bert-base-multilingual-cased-finetuned-openalex-topic-classification-title-abstract", 
            top_k=1, 
            truncation=True, 
            max_length=512
        )
        self.taxonomy_map = taxonomy_map

    def get_topic(self, title):
        output = self.classifier("<TITLE>" + title)[0][0]["label"]
        split = output.split(":")
        raw_topic = split[0]
        true_topic_id = str(int(raw_topic.strip()) + 10000)
        if true_topic_id in self.taxonomy_map:
            hierarchy = self.taxonomy_map[true_topic_id]
            return hierarchy["subfield"]
        else:
            return raw_topic


_extractor = None


def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = TopicExtractor()
    return _extractor


if __name__ == "__main__":
    extractor = TopicExtractor()
    extractor.get_topic("Effective Reductions of Mealy Machines.")