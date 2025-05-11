#!/usr/bin/env python3
import json, getopt, sys, csv
from pathlib import Path
from urllib import request
from ipdb import set_trace as trace

languages = {
        "slk": "SK",
        "ces": "CZ",
        "deu": "DE",
        "eng": "EN",
        "fra": "FR",
        }


DIGILIB_PATH = './data/digilib'
SOLR_HOST = 'localhost:8983'

class SolrException(Exception):
    def __init__(self, resp, payload):
        self.message = resp
        self.payload = payload

def book_load_pages(base_path, book):
    bookpath = Path(base_path) / book['ID/DirName']
    xiter = bookpath.glob('**/*.xml')
    xlist = [xml for xml in xiter]
    bid = xlist[0].stem[:-6]    #identifikator bez cisla
    xlist = ["/"+str(xml) for xml in xlist]
    xlist.sort()

    book_data = {
        "id": book['ID/DirName'],
        'source': 'enu_kniznica', 
        'date': f'{book["Year"]}-01-01T00:00:00Z', 
        'ocr_text': "+".join(xlist),
        'author': [book['Author']],
        'title': [book['Title']],
        'publisher': [book['Publisher']],
        'language': [languages[book['Tesseract language']]],
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

def usage():
    print("Load book alto data to solr")
    print("Usage: ",sys.argv[0]+ " path/to/file.csv ")

def parsecmd():
    try:
        opts, Names = getopt.getopt(sys.argv[1:], "h", [])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err)) # will print something like "option -a not recognized"
        usage(desc)
        sys.exit(2)
    for o, a in opts:
        if o in ("-h"):
            usage()
            sys.exit(0)
        else:
            assert False, "unhandled option"
    return Names

#['ID/DirName;Format;Source path;Title;Author;Tesseract language;Year;Publisher']
def loadCSV(ifile):
    hdr = None
    with open(ifile, 'rt', encoding='utf-8', newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=';', quotechar='"',quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            if not row: continue
            if not hdr:
                hdr = row
                continue
            rdir = {}
            for nn, val in enumerate(row):
                rdir[hdr[nn]] = val
            yield rdir

if __name__ == '__main__':
    #book = "modern_physics_krane"
    booksDir = parsecmd()
    if not booksDir:
        usage()
        sys.exit(0)

    books = loadCSV(booksDir[0])
    for book in books:
        print("indexing", book)
        book_dir = book_load_pages(DIGILIB_PATH, book)
        index_document([book_dir])
