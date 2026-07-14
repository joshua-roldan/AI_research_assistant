"""Serve an interactive Cytoscape.js view of the research knowledge graph."""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from neo4j import Driver

from .graph_data import NODE_COLORS, build_cytoscape_from_search_results, fetch_cytoscape_elements

DEFAULT_PORT = 8765

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Research Knowledge Graph</title>
  <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.75rem 1rem;
      background: #111827;
      border-bottom: 1px solid #1f2937;
    }
    h1 {
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
    }
    #search {
      width: 280px;
      max-width: 50vw;
      padding: 0.45rem 0.65rem;
      border-radius: 8px;
      border: 1px solid #334155;
      background: #0b1220;
      color: #e2e8f0;
    }
    #layout {
      display: grid;
      grid-template-columns: 1fr 320px;
      height: calc(100vh - 56px);
    }
    #cy {
      width: 100%;
      height: 100%;
      background: radial-gradient(circle at top, #172554 0%, #0f172a 45%);
    }
    aside {
      border-left: 1px solid #1f2937;
      background: #111827;
      padding: 1rem;
      overflow: auto;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.45rem;
      font-size: 0.9rem;
    }
    .swatch {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    #details {
      margin-top: 1rem;
      padding-top: 1rem;
      border-top: 1px solid #1f2937;
      font-size: 0.9rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .muted { color: #94a3b8; }
    @media (max-width: 900px) {
      #layout { grid-template-columns: 1fr; grid-template-rows: 1fr 240px; }
      aside { border-left: none; border-top: 1px solid #1f2937; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Research Knowledge Graph</h1>
    <input id="search" type="search" placeholder="Filter nodes by label..." />
  </header>
  <div id="layout">
    <div id="cy"></div>
    <aside>
      <div class="muted">Node types</div>
      <div id="legend"></div>
      <div id="details">Click a node to inspect its properties.</div>
    </aside>
  </div>
  <script>
    const elements = __GRAPH_DATA__;
    const nodeColors = __NODE_COLORS__;

    const legend = document.getElementById("legend");
    Object.entries(nodeColors).forEach(([type, color]) => {
      const item = document.createElement("div");
      item.className = "legend-item";
      item.innerHTML = `<span class="swatch" style="background:${color}"></span><span>${type}</span>`;
      legend.appendChild(item);
    });

    const cy = cytoscape({
      container: document.getElementById("cy"),
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: "#f8fafc",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "text-valign": "center",
            "text-halign": "center",
            width: 34,
            height: 34,
          },
        },
        {
          selector: 'node[type = "Paper"]',
          style: { width: 46, height: 46, "font-size": 11 },
        },
        {
          selector: 'node[type = "CodeRepository"]',
          style: { width: 40, height: 40, "background-color": "#C084FC", "font-size": 10 },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#64748b",
            "target-arrow-color": "#64748b",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: "#cbd5e1",
            "text-background-color": "#0f172a",
            "text-background-opacity": 0.75,
            "text-background-padding": 2,
          },
        },
        {
          selector: 'edge[label = "SIMILAR_TO"]',
          style: {
            "line-color": "#60a5fa",
            "target-arrow-color": "#60a5fa",
            width: "map(score, 0.75, 1, 2, 6)",
            "line-style": "dashed",
          },
        },
        {
          selector: ".highlighted",
          style: {
            "border-width": 3,
            "border-color": "#f8fafc",
          },
        },
        {
          selector: ".dimmed",
          style: { opacity: 0.15 },
        },
      ],
      layout: {
        name: "cose",
        animate: true,
        padding: 30,
        nodeRepulsion: 8000,
        idealEdgeLength: 90,
      },
    });

    const details = document.getElementById("details");
    function showDetails(node) {
      const data = node.data();
      const lines = [`Type: ${data.type}`, `Label: ${data.label}`];
      ["year", "doi", "venue", "source", "citation_count", "url", "abstract"].forEach((key) => {
        if (data[key] !== undefined && data[key] !== null && data[key] !== "") {
          lines.push(`${key}: ${data[key]}`);
        }
      });
      details.textContent = lines.join("\\n");
    }

    cy.on("tap", "node", (event) => {
      cy.elements().removeClass("highlighted dimmed");
      const node = event.target;
      const neighborhood = node.closedNeighborhood();
      cy.elements().addClass("dimmed");
      neighborhood.removeClass("dimmed");
      node.addClass("highlighted");
      showDetails(node);
    });

    cy.on("tap", (event) => {
      if (event.target === cy) {
        cy.elements().removeClass("highlighted dimmed");
        details.textContent = "Click a node to inspect its properties.";
      }
    });

    document.getElementById("search").addEventListener("input", (event) => {
      const term = event.target.value.trim().toLowerCase();
      cy.nodes().forEach((node) => {
        const visible = !term || node.data("label").toLowerCase().includes(term);
        node.style("display", visible ? "element" : "none");
      });
      cy.edges().forEach((edge) => {
        const visible =
          edge.source().style("display") !== "none" &&
          edge.target().style("display") !== "none";
        edge.style("display", visible ? "element" : "none");
      });
      cy.layout({ name: "cose", animate: true, padding: 30 }).run();
    });
  </script>
</body>
</html>
"""


def render_graph_html(elements: dict[str, list[dict[str, Any]]]) -> str:
    """Render the Cytoscape HTML page with embedded graph data."""
    graph_json = json.dumps(elements)
    colors_json = json.dumps(NODE_COLORS)
    return (
        HTML_TEMPLATE.replace("__GRAPH_DATA__", graph_json).replace(
            "__NODE_COLORS__", colors_json
        )
    )


def visualize_elements(
    elements: dict[str, list[dict[str, Any]]],
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    block: bool = True,
) -> ThreadingHTTPServer:
    """Serve a pre-built Cytoscape graph in the browser."""
    html = render_graph_html(elements)
    return _serve_html(html, port=port, open_browser=open_browser, block=block)


def _serve_html(
    html: str,
    *,
    port: int,
    open_browser: bool,
    block: bool,
) -> ThreadingHTTPServer:
    class GraphHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404, "Not Found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), GraphHandler)
    url = f"http://127.0.0.1:{port}/"
    node_count = html.count('"type": "Paper"') + html.count('"type": "Author"')
    print(f"Knowledge graph visualization running at {url}")

    if open_browser:
        webbrowser.open(url)

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping visualization server.")
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

    return server


def visualize_knowledge_graph(
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    driver: Driver | None = None,
    block: bool = True,
) -> ThreadingHTTPServer:
    """Start a local web server and open the graph in the default browser.

    Args:
        port: HTTP port for the visualization server.
        open_browser: Whether to open the default browser automatically.
        driver: Optional preconfigured Neo4j driver.
        block: If True, keep the server running until interrupted.

    Returns:
        The running ``ThreadingHTTPServer`` instance.
    """
    elements = fetch_cytoscape_elements(driver=driver)
    print(
        f"Loaded {len(elements['nodes'])} nodes and {len(elements['edges'])} edges."
    )
    return _serve_html(
        render_graph_html(elements),
        port=port,
        open_browser=open_browser,
        block=block,
    )


if __name__ == "__main__":
    visualize_knowledge_graph()
