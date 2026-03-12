import json
from pathlib import Path

def search_signs(query, labels_path):
    """Search for signs matching query"""
    with open(labels_path, 'r') as f:
        labels_data = json.load(f)
        labels_map = {int(k): v for k, v in labels_data['id_to_label'].items()}
    
    if not query:
        return list(labels_map.values())
    
    query_clean = query.lower().strip()
    matches = []
    
    for word in labels_map.values():
        word_clean = word.lower().strip()
        if query_clean in word_clean:
            matches.append(word)
    
    return matches