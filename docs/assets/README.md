# Report assets

`report.css` and `report.js` style the report and render its two Mermaid diagrams.
Serve the repository with `uv run python -m http.server 8000`, then open `/docs/`.

Mermaid is vendored so diagram rendering does not depend on a third-party CDN.

- Version: 11.12.0
- Upstream: https://github.com/mermaid-js/mermaid
- Bundle: https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.min.js
- License: `mermaid-LICENSE` (MIT)
- Integration reference: https://mermaid.js.org/config/usage.html

When upgrading, replace the versioned bundle and license, update the script path
in `index.html`, and check both diagrams in a browser, including with external
network requests blocked. Diagram sources live in the HTML; colors and rendering
options live in `report.js`. Diagram panels intentionally keep a light background
in both themes for legibility.
