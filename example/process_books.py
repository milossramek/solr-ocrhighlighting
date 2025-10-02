#!/usr/bin/env python3
import json, getopt, sys, csv, os, shutil
from pathlib import Path
from urllib import request
from dotenv import load_dotenv
from ipdb import set_trace as trace
from PIL import Image
import pytesseract, subprocess
from lxml import etree
from io import BytesIO
import pypdfium2 as pdfium

languages = {
        "slk": "SK",
        "ces": "CZ",
        "deu": "DE",
        "eng": "EN",
        "fra": "FR",
        }

load_dotenv()
DIGILIB_PATH = os.getenv('CFG_DIGILIB_PATH') # 'data/digilib'
SOLR_HOST = os.getenv('CFG_SOLR_HOST')       # 'localhost:8983

def disp(iimg):
    """ Display an image using pylab """
    import matplotlib
    matplotlib.interactive(True)
    matplotlib.pyplot.imshow(iimg, interpolation='none')


# pageId: page_0003
def alto_fixes(alto_root, pageId):
    # Namespace map (adjust if using ALTO v4)
    NS = {"alto": "http://www.loc.gov/standards/alto/ns-v3#"}

    # Update the <Page> ID
    page = alto_root.find(".//alto:Page", namespaces=NS)
    if page is not None:
        page.set("ID", pageId)   # pageId is your variable with new ID

    # Update all <fileName> nodes
    for node in alto_root.findall(".//alto:fileName", namespaces=NS):
        node.text = f"{pageId}.jpg"     # filename is your variable with new value

    # Merge hyphenated strings at line end
    all_strings = alto_root.findall(".//alto:String", namespaces=NS)
    i = 0
    while i < len(all_strings) - 1:
        s = all_strings[i]
        text = s.get("CONTENT", "")
        parent_line = s.getparent()

        # Check if this <String> ends with "-" and is the last one in its <TextLine>
        siblings = parent_line.findall(".//alto:String", namespaces=NS)
        is_last_in_line = (siblings and siblings[-1] is s)

        if text.endswith("-") and is_last_in_line:
            next_s = all_strings[i + 1]
            joined = text[:-1] + next_s.get("CONTENT", "")
            # Replace first part with the merged content
            s.set("CONTENT", joined)
            # Remove the second part from its parent
            next_s.getparent().remove(next_s)
            # Refresh list of <String> elements
            all_strings = alto_root.findall(".//alto:String", namespaces=NS)
        else:
            i += 1
    return alto_root

def rescale_alto_dimensions(alto_root, scale_factor):
    """
    Rescales all dimension attributes in an ALTO XML file based on a change in DPI.

    Args:
        alto_filepath (str): The path to the ALTO XML file.
        old_dpi (int): The original DPI of the image the ALTO was based on.
        new_dpi (int): The target DPI for the new image dimensions.
    """
    try:
        # Define the XML namespace (ALTO namespace is critical for lxml to work)
        # We assume the standard ALTO 2.1 or 3.0 namespace here.
        ns = {'alto': alto_root.nsmap.get(None, 'http://www.loc.gov/standards/alto/ns-v2#')}

    except etree.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    # 3. Define the Attributes to Rescale
    # ALTO dimension attributes: HPOS (Horizontal Position), VPOS (Vertical Position), WIDTH, HEIGHT
    dimension_attributes = ['HPOS', 'VPOS', 'WIDTH', 'HEIGHT']

    # 4. Iterate and Rescale Attributes
    
    # Use XPath to find all elements that contain any of the dimension attributes.
    # This is more efficient than iterating through every single element.
    # We select all elements whose names end in Block, Line, String, Glyph, or Space.
    xpath_query = (
        "//alto:TextBlock | //alto:TextLine | //alto:String | //alto:Glyph | "
        "//alto:Shape | //alto:PrintSpace | //alto:Page"
    )
    
    elements_to_update = alto_root.xpath(xpath_query, namespaces=ns)
    
    updates_count = 0

    for element in elements_to_update:
        for attr_name in dimension_attributes:
            
            # Check if the element has the attribute
            if attr_name in element.attrib:
                try:
                    # Get the current value and convert to float
                    original_value = float(element.attrib[attr_name])
                    
                    # Apply the scaling factor
                    new_value = original_value * scale_factor
                    
                    # Update the attribute, rounding to the nearest integer
                    # Since ALTO typically uses integer coordinates
                    element.attrib[attr_name] = str(round(new_value))
                    updates_count += 1
                    
                except ValueError:
                    # Skip if the attribute value is not a valid number
                    continue
    return alto_root

def ocr_image(img, lang):
    dpi = img.info['dpi']
    if dpi:
        #alto_xml = pytesseract.image_to_alto_xml(img, lang=lang, config=f"--dpi {dpi[0]}")
        alto_xml = pytesseract.image_to_alto_xml(img, lang=lang)
    else:
        alto_xml = pytesseract.image_to_alto_xml(img, lang=lang)
    return alto_xml

def get_page_dimensions(alto_root):
    """
    return page dimensions (width, height) from the <Page> element.
    """
    #alto_bytes = alto_str.encode('utf-8')

    # Namespace map (adjust for v3/v4 if needed)
    NS = {"alto": "http://www.loc.gov/standards/alto/ns-v3#"}

    page = alto_root.find(".//alto:Page", namespaces=NS)
    if page is not None:
        width = float(page.get("WIDTH"))
        height = float(page.get("HEIGHT"))
        return width, height
    else:
        raise ValueError("No <Page> element found in ALTO file")

#copy_and_process(book['Source path'], base_path, book['ID/DirName'], book['Tesseract language'])
def book_process_pages(base_path, book):
    source_path = book['Source path'] # directory with images or a pdf
    dest_name =  book['ID/DirName']
    lang = book['Tesseract language']
    book_format = book["Format"]

    basePath = Path(base_path)      #data/digilib
    bookPath = basePath / dest_name #data/digilib/Test_img
    imgPath = bookPath / dest_name  #data/digilib/Test_img/Test_img
    auxPath = bookPath / "aux"      #data/digilib/Test_img/aux (intermediate storage)

    # Remove existing stuff
    if bookPath.exists() and bookPath.is_dir():
        shutil.rmtree(bookPath)
    os.mkdir(bookPath)
    os.mkdir(imgPath)

    pages_json = {
            "title": dest_name,
            "pages": []
            }

    # Format specific stuff
    if book_format == "jpg" or book_format == "pdfimg":      
        os.mkdir(auxPath)
        if book_format == "pdfimg": 
            #extract images from pdf and save them to auxPath
            dpi = 200
            scale = dpi / 72  # PDF default is 72 DPI
            pdf = pdfium.PdfDocument(source_path)
            for i in range(len(pdf)):
                page = pdf[i]
                pil_image = page.render(scale=scale).to_pil()  # scale=1 ~ 72dpi
                # save to final destination
                pil_image.save(auxPath / f"page_{i+1:04d}.jpg", dpi=(dpi, dpi), quality=90)
        else: #img
            #rename and copy images to auxPath
            files = sorted(list(Path(source_path).glob("*.jpg")))
            for n, file  in enumerate(files):
                shutil.copy2(file, auxPath / f"{'page_%04d'%(n+1)}.jpg")
    
        # Preprocess the images and save them to imgPath - just copy for now
        files = sorted(list(auxPath.glob("*.jpg")))
        for n, file  in enumerate(files):
            shutil.copy2(file, imgPath)
        shutil.rmtree(auxPath)

        #OCR the images by tesseract
        files = sorted(list(imgPath.glob("*.jpg")))
        for n, file  in enumerate(files):
            img = Image.open(file)
            alto_bytes = ocr_image(img, lang=lang)    # alto_xml is bytes here
            # Parse with lxml
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(BytesIO(alto_bytes), parser)
            alto_root = tree.getroot()

            alto_root = alto_fixes(alto_root,file.stem)  # stem: file name without suffix
            # Save ALTO XML
            with open(bookPath / f"{'page_%04d'%(n+1)}.xml", "w", encoding="utf-8") as f:
                output_bytes = etree.tostring(alto_root, pretty_print=True, encoding="utf-8", xml_declaration=True)
                f.write(output_bytes.decode("utf-8"))
            width, height = get_page_dimensions(alto_root)
            pages_json["pages"].append(
                    {"page":str(n+1),"width":str(width),"height":str(height)},
                )
    else: #book_format == "pdftxt", "pdfocr"
        #extract alto per page and then extract images with the same resolution`
        pdf = pdfium.PdfDocument(source_path)
        for n in range(len(pdf)):
            page = pdf[n]
            cmd = ['/usr/local/bin/pdfalto', 
                   '-f', f'{n+1}',
                   '-l', f'{n+1}',
                   source_path,
                   "-"
                   ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,  # Capture stdout and stderr
                    text=True,            # Decode output as text (string)
                    check=True            # Raise an exception for non-zero exit codes
                )
                alto_xml = result.stdout
            except subprocess.CalledProcessError as e:
                print(f"Command failed with error code {e.returncode}")
                print(f"Error output (stderr):\n{e.stderr}")
            except FileNotFoundError:
                print(f"Error: The program '{cmd[0]}' was not found.")

            dpi = 200
            scale = dpi / 72  # PDF default is 72 DPI
            pil_image = page.render(scale=scale).to_pil()  # scale=1 ~ 72dpi
            #trace()
            pageId = 'page_%04d'%(n+1)
            alto_bytes = alto_xml.encode('utf-8')
            # Parse with lxml
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(BytesIO(alto_bytes), parser)
            alto_root = tree.getroot()
            alto_root = alto_fixes(alto_root,pageId)
            alto_root = rescale_alto_dimensions(alto_root, scale)
            with open(bookPath / f"{pageId}.xml", "w", encoding="utf-8") as f:
                output_bytes = etree.tostring(alto_root, pretty_print=True, encoding="utf-8", xml_declaration=True)
                f.write(output_bytes.decode("utf-8"))
            width, height = get_page_dimensions(alto_root)
            pages_json["pages"].append(
                    {"page":str(n+1),"width":str(width),"height":str(height)},
                )
            pil_image.save(imgPath / f"{pageId}.jpg")
    with open(bookPath / "pages.json", 'w') as f:
        json.dump(pages_json, f, indent=4)


def usage():
    print("Process source page images/pdfs and extract alto data")
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
    booksDir = parsecmd()
    if not booksDir:
        usage()
        sys.exit(0)

    books = loadCSV(booksDir[0])
    for book in books:
        print("indexing", book)
        book_dir = book_process_pages(DIGILIB_PATH, book)
'''
Delete all 'ocr' content
curl -X POST -H 'Content-Type: text/xml' -d '<delete><query>*:*</query></delete>' "http://localhost:8983/solr/ocr/update?commit=true"

Execute remotely
ssh digilib "cd /var/opt/solr-ocrhighlighting/example && ./ingest_digi.py data/digilib/skenDII.csv "
'''
'''
http://localhost:8181/viewer/?manifest=http://localhost:8181/iiif/presentation/Beliana9Test_pdf_img/manifest&cv=page_0001&q=horn%C3%A1du&title=Beliana9Test_pdf
http://localhost:8181/iiif/presentation/Beliana9Test_pdf_img/manifest
http://iiif.trigan2.local/iiif/2/Beliana9Test_pdf_img%2Fpage_0001.jpg  odlišná veľkosť strany
http://iiif.trigan2.local/iiif/2/Beliana9Test_pdf_img%2Fpage_0002.jpg

http://localhost:8181/viewer/?manifest=http://localhost:8181/iiif/presentation/Beliana9Test_img/manifest&cv=page_0001&q=horn%C3%A1du&title=Beliana9Test_img
http://localhost:8181/iiif/presentation/Beliana9Test_img/manifest
http://iiif.trigan2.local/iiif/2/Beliana9Test_img%2Fpage_0001.jpg  zhodná veľkosť strany
'''
