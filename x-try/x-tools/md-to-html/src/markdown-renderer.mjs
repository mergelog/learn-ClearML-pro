import MarkdownIt from "markdown-it";

const MERMAID_LANG = "mermaid";

/**
 * markdown-it インスタンスを生成する。
 * ```mermaid コードブロックだけは通常のコードハイライトではなく
 * <pre class="mermaid"> として出力し、ブラウザ側の mermaid.js に描画させる。
 */
function createMarkdownIt() {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    breaks: false,
  });

  const defaultFence =
    md.renderer.rules.fence ??
    ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));

  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    const lang = token.info.trim().split(/\s+/g)[0] ?? "";

    if (lang.toLowerCase() !== MERMAID_LANG) {
      return defaultFence(tokens, idx, options, env, self);
    }

    const code = md.utils.escapeHtml(token.content);
    return `<pre class="mermaid">${code}</pre>\n`;
  };

  return md;
}

/**
 * Markdown文字列をHTML断片（bodyの中身）に変換する。
 * @param {string} markdownSource
 * @returns {{ html: string, hasMermaid: boolean }}
 */
export function renderMarkdown(markdownSource) {
  const md = createMarkdownIt();
  const html = md.render(markdownSource);
  const hasMermaid = html.includes('class="mermaid"');
  return { html, hasMermaid };
}
