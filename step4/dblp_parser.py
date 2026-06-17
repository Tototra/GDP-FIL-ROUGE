import xml.etree.ElementTree as ET

from topic_modelling.topic_extractor import get_extractor


def parse_xml(pid, limit=None):
    with open(f"data/raw/author_{pid.replace('/', '_')}.xml", "r", encoding="utf-8") as f:
        xml_content = f.read()

    xml_content = xml_content.replace("<>", "<title>").replace("</>", "</title>")
    root = ET.fromstring(xml_content)
    author = root.find(".//person/author").text
    articles = (
        root.findall(".//article")
        + root.findall(".//inproceedings")
        + root.findall(".//phdthesis")
    )

    if limit is not None:
        articles = articles[:limit]

    extractor = get_extractor()

    publications = []
    for article in articles:
        coauthors = []
        for coauthor in article.findall("author"):
            if coauthor.text != author:
                coauthors.append((coauthor.get("pid"), coauthor.text))

        title_node = article.find("title")
        title = (
            "".join(title_node.itertext()).strip()
            if title_node is not None
            else "Untitled"
        )

        venue_node = {
            "Book": article.find(".//book"),
            "Journal": article.find(".//journal"),
            "School": article.find(".//school"),
            "Conference": article.find(".//booktitle"),
        }
        venue = next(
            (
                (origin, item.text)
                for origin, item in venue_node.items()
                if item is not None
            ),
            ("Unknown Origin", "Unknown Venue"),
        )

        year_node = article.find("year")
        year = year_node.text if year_node is not None else "Unknown Year"

        topic = extractor.get_topic(title)

        ee_node = article.find("ee")
        url = ee_node.text if ee_node is not None else ""

        publications.append((author, coauthors, title, topic, venue, year, url))

    return publications
