import requests
import json
import os

from transformers import pipeline

taxonomy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "openalex_taxonomy.json")

taxonomy_map = None
with open(taxonomy_path, "r", encoding="utf-8") as f:
    taxonomy_map = json.load(f)


class TopicExtractor:
    """
    A class for classifying article topics using OpenAlex's pre-trained model.
    
    Attributes:
        classifier: The OpenAlex BERT text classifier pipeline for topic classification
        taxonomy_map: Dictionary mapping OpenAlex topic IDs to their hierarchical
                     information (domain, field, subfield)
    """
    def __init__(self):
        """Initialize the TopicExtractor by loading the model and taxonomy mapping."""
        self.classifier = pipeline(
            "text-classification", 
            model="OpenAlex/bert-base-multilingual-cased-finetuned-openalex-topic-classification-title-abstract", 
            top_k=1, 
            truncation=True, 
            max_length=512
        )
        self.taxonomy_map = taxonomy_map

    def get_topic(self, title):
        """
        Extract and abstract the topic from an article title.

        Keeps the 'subfield' as it is more abstract and not too specific.
        
        Args:
            title: The article title string to classify
            
        Returns:
            The abstracted subfield topic, or raw topic if mapping not found
        """
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
    """Return a shared TopicExtractor instance, loading the model only on first call."""
    global _extractor
    if _extractor is None:
        _extractor = TopicExtractor()
    return _extractor


if __name__ == "__main__":
    extractor = TopicExtractor()
    extractor.get_topic("Effective Reductions of Mealy Machines.")