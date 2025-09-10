import "preact/debug";
import "./style";
import ResizeObserver from "resize-observer-polyfill";
import { Component } from "preact";
import { useState, useRef, useEffect, useMemo } from "preact/hooks";
import TextField from "preact-material-components/TextField";
import LinearProgress from "preact-material-components/LinearProgress";
import Typography from "preact-material-components/Typography";
import Elevation from "preact-material-components/Elevation";
import FormField from "preact-material-components/FormField";
import Checkbox from "preact-material-components/Checkbox";

import "preact-material-components/TextField/style.css";
import "preact-material-components/LinearProgress/style.css";
import "preact-material-components/Typography/style.css";
import "preact-material-components/Elevation/style.css";
import "preact-material-components/FormField/style.css";
import "preact-material-components/Checkbox/style.css";

var PARAMS = {
  fl: "id,issue_id,title,subtitle,author",
  "hl.fl": "title",
  "hl.ocr.fl": "ocr_text",
};
var IMAGE_API_BASE_B = "__CFG_IMAGE_API_BASE__";

if (typeof window !== "undefined") {
  var APP_BASE = `${window.location.protocol || "http:"}//${
    window.location.host
  }`;
} else {
  var APP_BASE = "__CFG_SERVER_URL__";
}

// Largely a 1:1 port of https://github.com/ZeeCoder/use-resize-observer (MIT-licensed) to Preact
function useResizeObserver({ ref, onResize }) {
  const defaultRef = useRef(null);

  if (!ref) {
    ref = defaultRef;
  }
  const [size, setSize] = useState({ width: undefined, height: undefined });
  const previous = useRef({ width: undefined, height: undefined });

  useEffect(() => {
    if (
      typeof ref !== "object" ||
      ref === null ||
      !(ref.current instanceof Element)
    ) {
      return;
    }

    const element = ref.current;
    const observer = new ResizeObserver((entries) => {
      if (!Array.isArray(entries) || !entries.length) {
        return;
      }

      const entry = entries[0];
      const newWidth = Math.round(entry.contentRect.width);
      const newHeight = Math.round(entry.contentRect.height);
      if (
        previous.current.width !== newWidth ||
        previous.current.height !== newHeight
      ) {
        const newSize = { width: newWidth, height: newHeight };
        if (onResize) {
          onResize(newSize);
        } else {
          previous.current.width = newWidth;
          previous.current.height = newHeight;
          setSize(newSize);
        }
      }
    });
    observer.observe(element);
    return () => observer.unobserve(element);
  }, [ref, onResize]);

  return useMemo(() => ({ ref, width: size.width, height: size.height }), [
    ref,
    size ? size.width : null,
    size ? size.height : null,
  ]);
}

function highlightDocument(doc, highlights) {
  Object.keys(highlights).forEach((field) => {
    if (Array.isArray(doc[field])) {
      doc[field] = doc[field].map((fval) =>
        highlightFieldValue(fval, highlights[field])
      );
    } else {
      doc[field] = highlightFieldValue(doc[field], highlights[field]);
    }
  });
  return doc;
}

function highlightFieldValue(val, highlights) {
  let out = val;
  highlights.forEach((hl) => {
    const rawText = hl.replace(/<\/?em>/g, "");
    if (out.indexOf(rawText) > -1) {
      out = out.split(rawText).join(hl);
    }
  });
  return out;
}

const HighlightDisplay = ({ scaleFactor, highlight }) => {
  const left = scaleFactor * highlight.ulx;
  const top = scaleFactor * highlight.uly;
  const width = scaleFactor * (highlight.lrx - highlight.ulx);
  const height = scaleFactor * (highlight.lry - highlight.uly);

  const style = {
    position: "absolute",
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
    backgroundColor: `hsla(50, 100%, 50%, 50%)`,
  };
  return <div style={style} title={highlight.text} />;
};

const RegionDisplay = ({
  manifestUri,
  page,
  title,
  region,
  highlights,
  query,
  getImageUrl,
}) => {
  const [scaleFactor, setScaleFactor] = useState(undefined);
  const { ref } = useResizeObserver({
    onResize: ({ width }) => setScaleFactor(width / (region.lrx - region.ulx)),
  });
  //Normalize snippet letter size. To make smaller/larger, change the factor XX *
  const dynamicWidth = __CFG_SNIPPET_SCALING__ * (region.lrx - region.ulx) / page.width;
  const viewerUrl = `/viewer/?manifest=${manifestUri}&cv=${page.id}&q=${query}&title=${title}`;
  return (
    <div class="region-display">
      <div class="region-img-container">
        <a href={viewerUrl} target="_blank" title="Stranu otvoriť v prehliadači Mirador">
          <img ref={ref} alt={region.text} src={getImageUrl(region, page)} style={{ width: `${dynamicWidth}vw` }}  />
        </a>
        {scaleFactor &&
          highlights.map((hl) => (
            <HighlightDisplay
              scaleFactor={scaleFactor}
              highlight={hl}
              key={`${hl.ulx}.${hl.uly}`}
            />
          ))}
      </div>
      <p class="highlightable" dangerouslySetInnerHTML={{ __html: region.text }} />
    </div>
  );
};

const SnippetDisplay = ({
  snippet,
  docId,
  docTitle,
  manifestUri,
  query,
  getImageUrl,
}) => {
  return (
    <div class="snippet-display">
      {snippet.regions.map((region, idx) => {
        const page = snippet.pages[region.pageIdx];
        const highlights = snippet.highlights
          .flatMap((hl) => hl)
          .filter((hl) => hl.parentRegionIdx === idx);
        return (
          <RegionDisplay
            key={`region-${docId}-${idx}`}
            getImageUrl={getImageUrl}
            manifestUri={manifestUri}
            page={page}
            title={docTitle}
            region={region}
            highlights={highlights}
            query={query}
          />
        );
      })}
    </div>
  );
};

const getImageUrl = (bookId, region, page, width) => {
    const x = parseInt(region.ulx);
    const y = parseInt(region.uly);
    const w = parseInt((region.lrx - region.ulx));
    const h = parseInt((region.lry - region.uly));
    const regionStr = `${x},${y},${w},${h}`;
    const widthStr = width ? `${width},` : "max";
    return `${IMAGE_API_BASE_B}/${bookId}%2F${page.id}.jpg/${regionStr}/${widthStr}/0/default.jpg`;
};

function DigilibResultDocument({ hl, ocr_hl, query, doc: initialDoc }) {
    const doc = highlightDocument(initialDoc, hl);
    const [isListVisible, setIsListVisible] = useState(false);

    useEffect(() => {
        setIsListVisible(false);
    }, [query]);

    const toggleListVisibility = () => {
        setIsListVisible(!isListVisible);
    };

    const pageIdx =
        (ocr_hl && ocr_hl.snippets && ocr_hl.snippets[0] &&
         ocr_hl.snippets[0].pages && ocr_hl.snippets[0].regions &&
         ocr_hl.snippets[0].regions[0])
            ? parseInt(ocr_hl.snippets[0].pages[ocr_hl.snippets[0].regions[0].pageIdx].id.substring(1)) - 1
            : 0;
    const manifestUri = `${APP_BASE}/iiif/presentation/${doc.id}/manifest`;
    const viewerUrl = `/viewer/?manifest=${manifestUri}&cv=${pageIdx}&q=${query}`;

    return (
        <div class="result-document">
            <Elevation z={4}>
                <div
                    onClick={toggleListVisibility}
                    style={{
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 0',
                    }}
                >
                    <span
                        style={{
                            marginRight: '8px',
                            transition: 'transform 0.2s ease-in-out',
                            transform: isListVisible ? 'rotate(90deg)' : 'rotate(0deg)',
                            fontSize: '1.2em',
                        }}
                    >
                        ►
                    </span>

                    <div
                        style={{
                            flexGrow: 1,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                        }}
                    >
                        <div>
                            <Typography tag="div" headline4>
                                <div style={{ color: 'blue' }} >
                                    {doc.author[0] + ", " + doc.title}
                                </div>
                            </Typography>
                            {doc.subtitle}
                        </div>

                        <Typography subtitle1 style={{ marginLeft: '16px' }}>
                            Počet výsledkov: {ocr_hl ? ocr_hl.numTotal : "Žiadne"}
                        </Typography>
                    </div>
                </div>

                {isListVisible && ocr_hl && ocr_hl.snippets && ocr_hl.snippets.length > 0 && (
                    ocr_hl.snippets.map((snip, idx) => (
                        <SnippetDisplay
                            key={idx}
                            snippet={snip}
                            docId={doc.issue_id}
                            docTitle={doc.title}
                            query={query}
                            manifestUri={manifestUri}
                            getImageUrl={(region, page, width) => getImageUrl(doc.id, region, page, width)}
                        />
                    ))
                )}
            </Elevation>
        </div>
    );
}

export default class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      isSearchPending: false,
      queryParams: {
        "df": "ocr_text",
        "hl.snippets": 1000,
        "hl.weightMatches": true,
        hl: "on",
        rows: 1000,
      },
      sources: ["gbooks", "lunion"],
      searchResults: undefined,
      isHelpVisible: false,
    };
  }

  onSubmit(evt) {
    if (evt) {
      evt.preventDefault();
    }
    const query = document.querySelector(".search-form input").value;
    const params = {
      ...this.state.queryParams,
      ...PARAMS,
      q: query,
    };
    if (this.state.sources.length == 1) {
      params.fq = "source:" + this.state.sources[0];
    }
    fetch(`${APP_BASE}/solr/ocr/select?${new URLSearchParams(params)}`)
      .then((resp) => resp.json())
      .then((data) =>
        this.setState({ searchResults: data, isSearchPending: false })
      )
      .catch((err) => {
        console.error(err);
        this.setState({ isSearchPending: false });
      });
    this.setState({
      isSearchPending: true,
      queryParams: params,
    });
  }

  onSliderChange(evt) {
    const val = evt.detail.value;
    if (typeof val === "number" && !Number.isNaN(val)) {
      this.setState({
        queryParams: {
          ...this.state.queryParams,
          "hl.snippets": val,
        },
      }, () => this.onSubmit());
    }
  }

  onSourceToggle(source, enabled) {
    let { sources } = this.state;
    if (enabled) {
      sources.push(source);
    } else {
      sources = sources.filter((s) => s !== source);
    }
    this.setState({
      sources,
    });
  }

  toggleHelpVisibility() {
    this.setState({
      isHelpVisible: !this.state.isHelpVisible
    });
  }

  render() {
    const { searchResults, isSearchPending, queryParams, sources } = this.state;
    return (
      <main>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/icon?family=Material+Icons"
        />
        <Typography tag="h1">
          __CFG_LIBRARY_NAME__
        </Typography>
        <form className="search-form" onSubmit={this.onSubmit.bind(this)}>
          <TextField
            disabled={isSearchPending || sources.length === 0}
            label="Hľadaný výraz"
            outlined
            trailingIcon="search"
          />
        </form>
        
        <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
          <Elevation z={1} style={{ padding: '4px', width: 'max-content' }}>
          <div
            onClick={this.toggleHelpVisibility.bind(this)}
            style={{
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '4px 0',
            }}
          >
            <span
              style={{
                marginRight: '6px',
                transition: 'transform 0.2s ease-in-out',
                transform: this.state.isHelpVisible ? 'rotate(90deg)' : 'rotate(0deg)',
                fontSize: '1em',
              }}
            >
              ►
            </span>
            <Typography tag="div" body2 style={{ fontWeight: 'normal' }}>
              Pravidlá na zadávanie dotazov
            </Typography>
          </div>

          {this.state.isHelpVisible && (
            <div style={{ paddingLeft: '24px', paddingBottom: '4px' }}>
              <Typography tag="div" body2>
                <ul style={{ margin: '4px 0', fontSize: '0.9em', textAlign: 'left' }}>
                  <li>Zadávajte s diakritikou, veľkosť písmen nerozhoduje</li>
                  <li>Pre vyhľadávanie fráz používajte úvodzovky: <code>"biely kôň"</code></li>
                  <li>Použite * na konci slova pre vyhľadávanie variant: <code>mačk*</code></li>
                  <li>Pre vyhľadávanie alternatív používajte OR: <code>pes OR mačka</code></li>
                  <li>Pre vyžadovanie oboch slov používajte AND: <code>kôň AND biely</code></li>
                  <li>Vylúčte slová pomocou NOT: <code>zviera NOT pes</code></li>
                  <li>Používajte zátvorky pre zoskupenie: <code>(pes OR mačka) AND domáci</code></li>
                  <li>Pre vyhľadávanie v blízkosti slov: <code>"kôň biely"~5</code></li>
                  <li>Špeciálne znaky (+ - && || ! ( ) { } [ ] ^ ~ * ? : \ /) musia byť escapované</li>
                  <li>Prázdny dotaz vráti všetky dokumenty</li>
                </ul>
              </Typography>
            </div>
          )}
          </Elevation>
        </div>
        {!isSearchPending && searchResults !== undefined && (
          <Typography tag="p" subtitle1>
            {searchResults.response.numFound === 0 
              ? "Hľadaný výraz nebol nájdený" 
              : `Hľadaný výraz bol nájdený v ${searchResults.response.numFound} dokumentoch za ${searchResults.responseHeader.QTime} ms.`
            }
          </Typography>
        )}
        <section class="results">
          {searchResults !== undefined &&
            searchResults.response.docs
              .map((doc, idx) => {
                return {
                  doc,
                  key: idx,
                  ocrHl: searchResults.ocrHighlighting[doc.id] ? searchResults.ocrHighlighting[doc.id].ocr_text : null,
                  hl: searchResults.highlighting[doc.id] || {},
                };
              })
              .sort((a, b) => (b.ocrHl && b.ocrHl.numTotal || 0) - (a.ocrHl && a.ocrHl.numTotal || 0))
              .map(({ key, doc, hl, ocrHl }) =>
                  <DigilibResultDocument
                    key={key}
                    hl={hl}
                    ocr_hl={ocrHl}
                    doc={doc}
                    query={queryParams.q}
                  />
              )}
        </section>
      </main>
    );
  }
}
