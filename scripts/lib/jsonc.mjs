/**
 * コメントと末尾コンマを許す JSON の読み取り。
 *
 * `tsconfig.json` は JSON ではなく JSONC で、`"lib": ["ES2024", "dom",]` の
 * ような末尾コンマとコメントを含みうる。検査スクリプトはこれらを読むため、
 * 素の `JSON.parse` では足りない。
 *
 * 正規表現でコメントや末尾コンマを落とす実装にしないのは、文字列の中身まで
 * 巻き込むため。実際 `"src/app/features/x/**\/*.ts"` は `/**\/` を空の
 * ブロックコメントとして含んでおり、正規表現で落とすと glob が別物になる。
 * 文字列の内と外を区別する必要があるので、1文字ずつ読む。
 */

const DOUBLE_QUOTE = '"';
const BACKSLASH = '\\';
const NO_PENDING_COMMA = -1;

/**
 * JSONC を `JSON.parse` が読める形へ正規化する。
 *
 * 文字列リテラルはそのまま通し、その外側にあるコメントと末尾コンマだけを
 * 空白へ置き換える。置き換えであって削除ではないのは、元の位置を保って
 * `JSON.parse` の報告する位置を読めるままにしておくため。
 */
function normalizeJsonc(text) {
  let result = '';
  // 直前に読んだコンマの位置。閉じ括弧が続けば末尾コンマだと分かる。
  let pendingComma = NO_PENDING_COMMA;
  let index = 0;

  while (index < text.length) {
    const character = text[index];

    if (character === DOUBLE_QUOTE) {
      const end = endOfString(text, index);
      result += text.slice(index, end);
      index = end;
      pendingComma = NO_PENDING_COMMA;
      continue;
    }

    if (character === '/' && text[index + 1] === '/') {
      const end = text.indexOf('\n', index);
      const stop = end === NO_PENDING_COMMA ? text.length : end;
      result += ' '.repeat(stop - index);
      index = stop;
      continue;
    }

    if (character === '/' && text[index + 1] === '*') {
      const end = text.indexOf('*/', index + 2);
      const stop = end === NO_PENDING_COMMA ? text.length : end + 2;
      result += blanked(text.slice(index, stop));
      index = stop;
      continue;
    }

    if (character === ',') {
      pendingComma = result.length;
    } else if (character === '}' || character === ']') {
      if (pendingComma !== NO_PENDING_COMMA) {
        result = `${result.slice(0, pendingComma)} ${result.slice(pendingComma + 1)}`;
      }
      pendingComma = NO_PENDING_COMMA;
    } else if (!isWhitespace(character)) {
      pendingComma = NO_PENDING_COMMA;
    }

    result += character;
    index += 1;
  }

  return result;
}

export function parseJsonc(text) {
  return JSON.parse(normalizeJsonc(text));
}

/**
 * `index` の引用符から始まる文字列リテラルの、閉じ引用符の次の位置を返す。
 */
function endOfString(text, index) {
  let cursor = index + 1;

  while (cursor < text.length) {
    if (text[cursor] === BACKSLASH) {
      cursor += 2;
      continue;
    }
    if (text[cursor] === DOUBLE_QUOTE) {
      return cursor + 1;
    }
    cursor += 1;
  }

  return text.length;
}

// 改行だけは残す。落とすと `JSON.parse` の報告する行番号がずれる。
const blanked = (text) => text.replace(/[^\n]/g, ' ');

const isWhitespace = (character) => character === ' ' || character === '\t' || character === '\n' || character === '\r';
