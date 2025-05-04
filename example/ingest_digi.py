#!/usr/bin/env python3
import json
from pathlib import Path
from urllib import request
from ipdb import set_trace as trace


DIGILIB_PATH = './data/digilib'
SOLR_HOST = 'localhost:8983'

class SolrException(Exception):
    def __init__(self, resp, payload):
        self.message = resp
        self.payload = payload

def book_load_pages(base_path, book):
    bookpath = Path(base_path) / book
    popispath = bookpath / "popis.json"
    with popispath.open("r") as json_data:
        jbook = json.load(json_data)
        json_data.close()
    
    xiter = bookpath.glob('**/*.xml')
    xlist = [xml for xml in xiter]
    bid = xlist[0].stem[:-6]    #identifikator bez cisla
    xlist = ["/"+str(xml) for xml in xlist]
    xlist.sort()

    book_data = {
        "id": jbook["identifikator"],
        'source': 'enu_kniznica', 
        'date': f'{jbook["rok"]}-01-01T00:00:00Z', 
        'ocr_text': "+".join(xlist),
        'author': [jbook['autor']],
        'title': [jbook['nazov']],
        'language': [jbook['jazyk']],
    }
    return book_data

def index_document(docs):
    req = request.Request(
        "http://{}/solr/ocr/update?softCommit=true".format(SOLR_HOST),
        data=json.dumps(docs).encode('utf8'),
        headers={'Content-Type': 'application/json'})
    resp = request.urlopen(req)
    if resp.status >= 400:
        raise SolrException(json.loads(resp.read()), docs)

if __name__ == '__main__':
    #book = "modern_physics_krane"
    books = ["beliana9b","MFKrane"]
    for book in books:
        print("indexing", book)
        book_dir = book_load_pages(DIGILIB_PATH, book)
        index_document([book_dir])
