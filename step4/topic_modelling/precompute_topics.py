import os
import glob
import xml.etree.ElementTree as ET
import json
from topic_extractor import TopicExtractor

def precompute_topics():
    print("Initializing TopicExtractor...")
    extractor = TopicExtractor()
    
    title_to_topic = {}
    
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
    xml_files = glob.glob(os.path.join(raw_dir, "*.xml"))
    
    print(f"Found {len(xml_files)} XML files.")
    
    unique_titles = set()
    
    for file_path in xml_files:
        with open(file_path, "r", encoding="utf-8") as f:
            xml_content = f.read()
            
        xml_content = xml_content.replace("<>", "<title>").replace("</>", "</title>")
        try:
            root = ET.fromstring(xml_content)
            articles = root.findall(".//article") + root.findall(".//inproceedings") + root.findall(".//phdthesis")
            for article in articles:
                title_node = article.find("title")
                if title_node is not None and title_node.text:
                    unique_titles.add(title_node.text)
        except ET.ParseError as e:
            print(f"Error parsing {file_path}: {e}")
            
    print(f"Found {len(unique_titles)} unique titles. Computing topics...")
    
    Total = len(unique_titles)
    for i, title in enumerate(unique_titles, 1):
        try:
            topic = extractor.get_topic(title)
            title_to_topic[title] = topic
        except Exception as e:
            print(f"Error computing topic for '{title}': {e}")
            title_to_topic[title] = "Unknown"
            
        if i % 100 == 0:
            print(f"Processed {i}/{Total} titles...")
            
    output_path = os.path.join(os.path.dirname(__file__), "data", "precomputed_topics.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(title_to_topic, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully saved {len(title_to_topic)} topics to {output_path}")

if __name__ == "__main__":
    precompute_topics()
