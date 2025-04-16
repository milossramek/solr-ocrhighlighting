#!/usr/bin/env python3
import itertools
import json
import re
import sys
import tarfile
import xml.etree.ElementTree as etree
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request
from ipdb import set_trace as trace


GOOGLE1000_PATH = './data/google1000'
GOOGLE1000_URL = 'https://ocrhl.jbaiter.de/data/google1000_texts.tar.gz'
GOOGLE1000_NUM_VOLUMES = 1000
SOLR_HOST = 'localhost:8983'
HOCR_METADATA_PAT = re.compile(
    r'<meta name=[\'"]DC\.(?P<key>.+?)[\'"] content=[\'"](?P<value>.+?)[\'"]\s*/?>')
NSMAP = {
    'mets': 'http://www.loc.gov/METS/',
    'mods': 'http://www.loc.gov/mods/v3'
}


class SolrException(Exception):
    def __init__(self, resp, payload):
        self.message = resp
        self.payload = payload


def gbooks_are_volumes_missing(base_path):
    for vol_no in range(1000):
        vol_path = base_path / 'Volume_{:04}.hocr'.format(vol_no)
        if not vol_path.exists():
            return True
    return False


def gbooks_parse_metadata(hocr):
    # I know, the <center> won't hold, but I think it's okay in this case,
    # especially since we 100% know what data this script is going to work with
    # and we don't want an external lxml dependency in here
    raw_meta =  {key: int(value) if value.isdigit() else value
                 for key, value in HOCR_METADATA_PAT.findall(hocr)}
    return {
        'author': [raw_meta.get('creator')] if 'creator' in raw_meta else [],
        'title': [raw_meta['title']],
        'date': '{}-01-01T00:00:00Z'.format(raw_meta['date']),
        **{k: v for k, v in raw_meta.items()
           if k not in ('creator', 'title', 'date')}
    }


def gbooks_load_documents(base_path):
    for doc_path in base_path.glob('*.hocr'):
        hocr = doc_path.read_text()
        yield {'id': doc_path.stem.split("_")[1],
               'source': 'gbooks',
               'ocr_text': '/data/google1000/' + doc_path.name,
               **gbooks_parse_metadata(hocr)}

def index_documents(docs):
    req = request.Request(
        "http://{}/solr/ocr/update?softCommit=true".format(SOLR_HOST),
        data=json.dumps(docs).encode('utf8'),
        headers={'Content-Type': 'application/json'})
    resp = request.urlopen(req)
    if resp.status >= 400:
        raise SolrException(json.loads(resp.read()), docs)


def generate_batches(it, chunk_size):
    cur_batch = []
    for x in it:
        cur_batch.append(x)
        if len(cur_batch) == chunk_size:
            yield cur_batch
            cur_batch = []
    if cur_batch:
        yield cur_batch


if __name__ == '__main__':
    gbooks_iter = gbooks_load_documents(Path(GOOGLE1000_PATH))
    batch = [it for it in gbooks_iter] 
    for book in batch:
        index_documents([book])
