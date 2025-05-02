import copy
from pathlib import Path

import lxml.etree as etree

from common import make_id, MANIFEST_TEMPLATE, CANVAS_TEMPLATE

import logging
logger = logging.getLogger(__name__)


def make_manifest(app, vol_id):
    base_dir = Path(app.config.get('GOOGLE1000_PATH', '../data/google1000'))
    logger.info(f"GGGGGGGGGGGGGGGGGG Making manifest for {base_dir}")
    hocr_path =  base_dir / f'Volume_{vol_id.split(":")[1]}.hocr'
    logger.info(f"GGGGGGGGGGGGGGGGGG hocr_path {hocr_path}")
    protocol = app.config.get('PROTOCOL', 'http')
    logger.info(f"GGGGGGGGGGGGGGGGGG protocol {protocol}")
    location = app.config.get('SERVER_NAME', 'localhost:8008')
    logger.info(f"GGGGGGGGGGGGGGGGGG SERVER_NAME {location}")
    app_path = app.config.get('APP_PATH', '')
    logger.info(f"GGGGGGGGGGGGGGGGGG APP_PATH {app_path}")
    manifest_path = app.url_for('get_manifest', volume_id=vol_id)
    logger.info(f"GGGGGGGGGGGGGGGGGG manifest_path {manifest_path}")
    search_path = app.url_for('search', doc_id=vol_id)
    logger.info(f"GGGGGGGGGGGGGGGGGG search_path {search_path}")
    image_api_base = app.config.get('IMAGE_API_BASE', 'http://localhost:8080')
    logger.info(f"GGGGGGGGGGGGGGGGGG image_api_base {image_api_base}")
    manifest = copy.deepcopy(MANIFEST_TEMPLATE)
    manifest['@id'] = f'{protocol}://{location}{app_path}/{manifest_path}'
    manifest['service']['@id'] = f'{protocol}://{location}{app_path}{search_path}'
    manifest['sequences'][0]['@id'] = make_id(app, vol_id, 'sequence')
    tree = etree.parse(str(hocr_path))
    metadata = {}
    for meta_elem in tree.findall('.//meta'):
        if not meta_elem.attrib.get('name', '').startswith('DC.'):
            continue
        metadata[meta_elem.attrib['name'][3:]] = meta_elem.attrib['content']
    manifest['label'] = metadata.get('title', vol_id)
    manifest['metadata'] = [{'@label': k, '@value': v} for k, v in metadata.items()]
    for page_elem in tree.findall('.//div[@class="ocr_page"]'):
        canvas = copy.deepcopy(CANVAS_TEMPLATE)
        page_id = page_elem.attrib['id']
        canvas['@id'] = f'{protocol}://{location}{app_path}/{vol_id}/canvas/{page_id}'
        page_idx = int(page_id.split('_')[-1]) - 1
        image_url = f'{image_api_base}/{vol_id}_{page_idx:04}'
        _, _, width, height = (int(x) for x in page_elem.attrib['title'].split(' ')[1:])
        canvas['width'] = width
        canvas['height'] = height
        canvas['images'][0]['on'] = canvas['@id']
        canvas['images'][0]['resource']['width'] = width
        canvas['images'][0]['resource']['height'] = height
        canvas['images'][0]['resource']['@id'] = f'{image_url}/full/full/0/default.jpg'
        canvas['images'][0]['resource']['service']['@id'] = image_url
        manifest['sequences'][0]['canvases'].append(canvas)
    return manifest
