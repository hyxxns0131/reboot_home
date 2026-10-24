import json
from pathlib import Path

def get_all_products():
    return json.loads((Path(__file__).parent / 'data/products.json').read_text())

def get_product(slug):
    return next((p for p in get_all_products() if p['slug'] == slug), None)
