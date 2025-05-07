import copy, json
from pathlib import Path

from common import make_id, MANIFEST_TEMPLATE, CANVAS_TEMPLATE, NSMAP

def make_manifest(app, vol_id):
    base_dir = Path(app.config.get('DIGILIB_PATH', '../data/digilib'))
    protocol = app.config.get('PROTOCOL', 'http')
    location = app.config.get('SERVER_NAME', 'localhost:8181')
    app_path = app.config.get('APP_PATH', '/iiif/presentation')
    manifest_path = app.url_for('get_manifest', volume_id=vol_id)
    search_path = app.url_for('search', doc_id=vol_id)
    image_api_base = app.config.get('DIMAGE_API_BASE', 'https://iiif.beliana.sav.sk/iiif/2')
    
    with open(base_dir / vol_id / f"{vol_id}.json", "r") as fp:
        orig_manifest = json.load(fp)

    manifest = copy.deepcopy(MANIFEST_TEMPLATE)
    manifest['@id'] = f'{protocol}://{location}{app_path}/{manifest_path}'
    manifest['service']['@id'] = f'{protocol}://{location}{app_path}{search_path}'
    manifest["behavior"] = "individuals"
    manifest['sequences'][0]['@id'] = make_id(app, vol_id, 'sequence')
    manifest['attribution'] = "Digitálna knižnica EnÚ SAV"
    manifest['label'] = orig_manifest['label']
    #manifest['metadata'] = copy.deepcopy(orig_manifest['metadata'])
    for page_elem in orig_manifest['sequences'][0]['canvases']:
        canvas = copy.deepcopy(CANVAS_TEMPLATE)
        page_num = int(page_elem['label'].split(' ')[1])
        page_id = "page_%03d"%page_num  #page numbering by page_xxx specified in alto xml files
        canvas['@id'] = f'{protocol}://{location}{app_path}/{vol_id}/canvas/{page_id}'
        canvas['label'] = str(page_num)
        canvas['images'][0]['on'] = canvas['@id']
        canvas["width"] = page_elem["width"]
        canvas["height"] = page_elem["height"]
        canvas['images'][0]['resource']['width'] = page_elem['width']
        canvas['images'][0]['resource']['height'] = page_elem['height']

        image_url = f'{image_api_base}/{vol_id}'
        #canvas['images'][0]['@id'] = canvas['@id']
        #canvas['images'][0]['resource']['@id'] = f'{image_url}%2F{page_id}.jpg'
        #canvas['images'][0]['resource']['service']['@id'] = canvas['images'][0]['resource']['@id']
        canvas['images'][0]['resource']['@id'] = f'{image_url}%2F{page_id}.jpg/full/full/0/default.jpg'
        canvas['images'][0]['resource']['service']['@id'] = f'{image_url}%2F{page_id}.jpg'
        #canvas['images'][0]['resource']['@id'] = f'{image_url}%2F{vol_id}/{page_id}.jpg/full/full/0/default.jpg'

        manifest['sequences'][0]['canvases'].append(canvas)
    return manifest
