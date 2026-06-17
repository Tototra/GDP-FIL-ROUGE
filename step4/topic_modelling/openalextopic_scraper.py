"""
This file allows us to request the OpenAlex's API to get the different
research topics, and store it in 'data/openalex_taxonomy.json' file as
a lookup table.
"""
import requests
import json

url = "https://api.openalex.org/topics"
params = {
    "per_page": 200,
    "cursor": "*",
}

taxonomy_map = {}

print("Starting download of OpenAlex topics taxonomy...")

while params["cursor"]:
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        break
        
    data = response.json()
    results = data.get("results", [])
    
    if not results:
        break
        
    for topic in results:
        raw_id = topic["id"].split("/")[-1].replace("T", "")
        
        taxonomy_map[raw_id] = {
            "topic_name": topic.get("display_name"),
            "subfield": topic.get("subfield", {}).get("display_name"),
            "field": topic.get("field", {}).get("display_name"),
            "domain": topic.get("domain", {}).get("display_name")
        }
        
    params["cursor"] = data.get("meta", {}).get("next_cursor")
    print(f"Fetched {len(taxonomy_map)} topics...")

with open("data/openalex_taxonomy.json", "w", encoding="utf-8") as f:
    json.dump(taxonomy_map, f, indent=2)

print("Finished. Taxonomy saved to data/openalex_taxonomy.json")