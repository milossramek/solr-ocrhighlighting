#!/usr/bin/env python3
import itertools
import json
import re
import sys
import tarfile
import xml.etree.ElementTree as etree
#from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request
from ipdb import set_trace as trace


LUNION_PATH = './data/bnl_lunion'
LUNION_TEXTS_URL = 'https://ocrhl.jbaiter.de/data/bnl_lunion_texts.tar.gz'
LUNION_NUM_ARTICLES = 41446
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

def bnl_get_metadata(mods_tree):
    authors = []
    name_elems = mods_tree.findall('.//mods:name', namespaces=NSMAP)
    for name_elem in name_elems:
        role = name_elem.findtext('.//mods:roleTerm', namespaces=NSMAP)
        if role == 'aut':
            authors.append(" ".join(e.text for e in 
                name_elem.findall('.//mods:namePart', namespaces=NSMAP)))
    return {
        'author': authors,
        'title': [e.text for e in mods_tree.findall(".//mods:title",
                                                    namespaces=NSMAP)],
        'subtitle': [e.text for e in mods_tree.findall(".//mods:subTitle",
                                                       namespaces=NSMAP)]
    }


def bnl_get_article_pointer(path_regions):
    grouped = {
        p: sorted(bid for bid, _ in bids)
        for p, bids in itertools.groupby(path_regions, key=lambda x: x[1])}
    pointer_parts = []
    for page_path, block_ids in grouped.items():
        local_path = Path(LUNION_PATH) / page_path
        regions = []
        with local_path.open('rb') as fp:
            page_bytes = fp.read()
        for block_id in block_ids:
            start_match = re.search(
                rb'<([A-Za-z]+?) ID="%b"' % (block_id.encode()), page_bytes)
            start = start_match.start()
            end_tag = b'</%b>' % (start_match.group(1),)
            end = page_bytes.index(end_tag, start) + len(end_tag)
            regions.append((start, end))
        pointer_parts.append(
            '/data/bnl_lunion/{}[{}]'.format(
                page_path,
                ','.join('{}:{}'.format(*r) for r in sorted(regions))))
    return '+'.join(pointer_parts)


def bnl_extract_article_docs(issue_id, mets_path, alto_basedir):
    mets_tree = etree.parse(str(mets_path))
    article_elems = mets_tree.findall(
        ".//mets:structMap[@TYPE='LOGICAL']//mets:div[@TYPE='ARTICLE']",
        namespaces=NSMAP)
    title_info = mets_tree.find(
        ".//mets:dmdSec[@ID='MODSMD_PRINT']//mods:titleInfo",
        namespaces=NSMAP)
    newspaper_title = title_info.findtext('./mods:title', namespaces=NSMAP)
    newspaper_part = title_info.findtext('./mods:partNumber', namespaces=NSMAP)
    file_mapping = {
        e.attrib['ID']: next(iter(e)).attrib['{http://www.w3.org/1999/xlink}href'][9:]
        for e in mets_tree.findall('.//mets:fileGrp[@USE="Text"]/mets:file',
                                   namespaces=NSMAP)}
    out = []
    for elem in article_elems:
        meta_id = elem.attrib['DMDID']
        path_regions = [
            (e.attrib['BEGIN'],
             alto_basedir.parent.name + '/' + file_mapping.get(e.attrib['FILEID']))
            for e in elem.findall('.//mets:fptr//mets:area',
                                  namespaces=NSMAP)]
        mods_meta = mets_tree.find(
            './/mets:dmdSec[@ID="{}"]//mods:mods'.format(meta_id),
            namespaces=NSMAP)
        issue_date = mets_tree.findtext('.//mods:dateIssued', namespaces=NSMAP)
        article_no = meta_id.replace("MODSMD_ARTICLE", "")
        out.append({
            'id': '{}-{}'.format(issue_id, article_no),
            'source': 'bnl_lunion',
            'issue_id': issue_id,
            'date': issue_date + 'T00:00:00Z',
            'newspaper_title': newspaper_title,
            'newspaper_part': newspaper_part,
            'ocr_text': bnl_get_article_pointer(path_regions),
            **bnl_get_metadata(mods_meta),
        })
    return out


def bnl_are_volumes_missing(base_path):
    num_pages = sum(1 for _ in base_path.glob("*/text/*.xml"))
    #return num_pages != 10880
    return num_pages != 8

def _bnl_load_documents(base_path):
    if not base_path.exists():
        base_path.mkdir()
    if bnl_are_volumes_missing(base_path):
        print("Downloading missing BNL/L'Union issues to {}".format(base_path))
        base_path.mkdir(exist_ok=True)
        with request.urlopen(LUNION_TEXTS_URL) as resp:
            tf = tarfile.open(fileobj=resp, mode='r|gz')
            last_vol = None
            for ti in tf:
                sanitized_name = re.sub(r'^\./?', '', ti.name)
                if not sanitized_name:
                    continue
                if ti.isdir() and '/' not in sanitized_name:
                    if last_vol is not None:
                        vol_path = base_path / last_vol
                        mets_path = next(iter(vol_path.glob("*-mets.xml")))
                        vol_id = last_vol.replace("newspaper_lunion_", "")
                        yield from bnl_extract_article_docs(
                            vol_id, mets_path, vol_path / 'text')
                    last_vol = sanitized_name
                if ti.isdir():
                    (base_path / ti.name).mkdir(parents=True, exist_ok=True)
                else:
                    out_path = base_path / ti.name
                    with out_path.open('wb') as fp:
                        fp.write(tf.extractfile(ti).read())
            vol_path = base_path / last_vol
            mets_path = next(iter(vol_path.glob("*-mets.xml")))
            vol_id = last_vol.replace("newspaper_lunion_", "")
            yield from bnl_extract_article_docs(
                vol_id, mets_path, vol_path / 'text')
    else:
        #with ProcessPoolExecutor(max_workers=4) as pool:
        for issue_dir in base_path.iterdir():
            if not issue_dir.is_dir() or not issue_dir.name.startswith('15'):
                continue
            mets_path = next(iter(issue_dir.glob("*-mets.xml")))
            vol_id = issue_dir.name.replace("newspaper_lunion_", "")
            rslt = bnl_extract_article_docs(vol_id, mets_path, issue_dir / 'text')
            yield rslt

def bnl_load_documents(base_path):
    for issue_dir in base_path.iterdir():
        if not issue_dir.is_dir() or not issue_dir.name.startswith('15'):
            continue
        mets_path = next(iter(issue_dir.glob("*-mets.xml")))
        vol_id = issue_dir.name.replace("newspaper_lunion_", "")
        #vol_id: '1534425_1861-01-01'
        #mets_path: PosixPath('data/bnl_lunion/1534425_newspaper_lunion_1861-01-01/1534425_newspaper_lunion_1861-01-01-mets.xml')
        # issue_dir / 'text': PosixPath('data/bnl_lunion/1534425_newspaper_lunion_1861-01-01/text')
        rslt = bnl_extract_article_docs(vol_id, mets_path, issue_dir / 'text')
        yield rslt


def index_documents(docs):
    req = request.Request(
        "http://{}/solr/ocr/update?softCommit=true".format(SOLR_HOST),
        data=json.dumps(docs).encode('utf8'),
        headers={'Content-Type': 'application/json'})
    resp = request.urlopen(req)
    if resp.status >= 400:
        raise SolrException(json.loads(resp.read()), docs)


if __name__ == '__main__':
        print("Indexing BNL/L'Union articles")
        bnl_iter = bnl_load_documents(Path(LUNION_PATH))
        batch = [it for it in bnl_iter] 
        longbatch = []
        for bb in batch:
            longbatch += bb
        index_documents(longbatch)

'''
Delete all 'ocr' content
curl -X POST -H 'Content-Type: text/xml' -d '<delete><query>*:*</query></delete>' "http://localhost:8983/solr/ocr/update?commit=true"
docker 
 docker-compose up -d
 docker-compose down
 docker container ls
 docker image ls
 docker rmi 970e7fc0eac1
 docker exec -it ebf89d7faa4a bash #prezi
 docker exec -it  bash #prezi

Rebuild a container:
 docker stop example-iiif-prezi-1
 docker rm example-iiif-prezi-1
 cd iiif-prezi  #Where the Dockerfile is
 docker build -t example-iiif-prezi . #The dot!
 cd ..
 docker-compose up -d
'''
