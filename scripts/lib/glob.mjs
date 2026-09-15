/**
 * 宣言ファイルに書かれた glob を正規表現へ写す。
 *
 * `web-boundaries.json`、`tsconfig.strict.json` の `include`、
 * `test-pyramid.json` の3つが、検査対象を glob で宣言する。同じ書き方が
 * 場所によって違う意味にならないよう、変換はここ1か所に置く。
 *
 * - `*`      1階層の中の任意（`/` を跨がない）
 * - `**`     任意の深さ。**0階層でもよい**（`a/**\/*.ts` は `a/x.ts` に当たる）
 * - 末尾 `/**` 「その配下すべて」。配下に何かがあることは求めない
 */

export function globToRegExp(glob) {
  const pattern = glob
    .split('/')
    .map((segment) => {
      if (segment === '**') {
        return '(?:.+)';
      }
      return segment.split('*').map(escapeRegExp).join('[^/]*');
    })
    .join('/')
    .split('/(?:.+)/')
    .join('/(?:.+/)?')
    .replace(/\/\(\?:\.\+\)$/, '(?:/.+)?');

  return new RegExp(`^${pattern}$`);
}

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export const matchesAny = (path, globs) =>
  globs.some((glob) => globToRegExp(glob).test(path));
