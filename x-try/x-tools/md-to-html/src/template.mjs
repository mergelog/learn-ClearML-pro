const MERMAID_CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

const STYLE = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 2rem 1rem 4rem;
    background: #ffffff;
    color: #1f2328;
    font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Yu Gothic",
      "Noto Sans JP", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.8;
  }
  main {
    max-width: 860px;
    margin: 0 auto;
  }
  h1, h2, h3, h4, h5, h6 {
    line-height: 1.5;
    margin: 2em 0 0.8em;
    font-weight: 700;
  }
  h1 { font-size: 1.8em; border-bottom: 2px solid #d0d7de; padding-bottom: 0.3em; }
  h2 { font-size: 1.4em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; }
  h3 { font-size: 1.15em; }
  p, ul, ol, table, blockquote { margin: 0.8em 0; }
  ul, ol { padding-left: 1.6em; }
  li { margin: 0.3em 0; }
  a { color: #0969da; }
  code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    background: #f6f8fa;
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.9em;
  }
  pre {
    background: #f6f8fa;
    padding: 1em;
    border-radius: 6px;
    overflow-x: auto;
  }
  pre code {
    background: none;
    padding: 0;
    font-size: 0.85em;
  }
  pre.mermaid {
    background: transparent;
    text-align: center;
    padding: 1em 0;
  }
  blockquote {
    margin-left: 0;
    padding: 0.2em 1em;
    border-left: 4px solid #d0d7de;
    color: #57606a;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    display: block;
    overflow-x: auto;
  }
  th, td {
    border: 1px solid #d0d7de;
    padding: 0.5em 0.8em;
    text-align: left;
  }
  th {
    background: #f6f8fa;
  }
  img { max-width: 100%; }
  hr { border: none; border-top: 1px solid #d0d7de; margin: 2em 0; }
`;

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * 変換後の本文HTMLを、単体で開ける完結したHTMLドキュメントに包む。
 * @param {{ title: string, bodyHtml: string, hasMermaid: boolean }} params
 * @returns {string}
 */
export function wrapHtmlDocument({ title, bodyHtml, hasMermaid }) {
  const mermaidScript = hasMermaid
    ? `
    <script type="module">
      import mermaid from "${MERMAID_CDN_URL}";
      mermaid.initialize({ startOnLoad: true });
    </script>`
    : "";

  return `<!doctype html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>${STYLE}</style>
</head>
<body>
<main>
${bodyHtml}
</main>${mermaidScript}
</body>
</html>
`;
}
