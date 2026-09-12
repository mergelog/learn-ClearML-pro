import published from '~/features/data-catalog/data-catalog.surface.published.json';
import {catalogSurface, surfaceDrift} from '~/features/data-catalog/data-catalog.surface';

/**
 * 外へ公開している面が、黙って変わっていないことを確かめる。
 *
 * 台帳の出口は2つあり（参照URL と 書き出し）、どちらも**渡された時点の形**を
 * 前提に読まれる。守るのは形そのものではなく、形が黙って変わらないことである
 * （ADR 010 §4。考え方は ADR 006 と同じ）。
 *
 * **検知は完全一致、分類は説明。** 差分があればどんな差分でも落ちる。
 * 分類を検知に使うと、分類できない種類の変更が緑になる。
 */

describe('published catalog surface', () => {
  it('matches what is committed as published', () => {
    // 落ちたら、失敗の文言が「いまの面」をそのまま出す。意図した変更なら
    // data-catalog.surface.published.json をその内容へ直し、差分をレビューに載せる。
    expect(surfaceDrift(published, catalogSurface())).toBeNull();
  });
});

describe('reading the drift', () => {
  const current = catalogSurface();

  const changed = (mutate: (surface: ReturnType<typeof catalogSurface>) => void) => {
    const copy = JSON.parse(JSON.stringify(current)) as ReturnType<typeof catalogSurface>;
    mutate(copy);
    return copy;
  };

  it('calls a renamed query key breaking, because URLs already handed out stop filtering', () => {
    const before = changed((surface) => {
      surface.reference.queryKeys = {...surface.reference.queryKeys, text: 'query'};
    });

    const drift = surfaceDrift(before, current);

    expect(drift).toContain('渡した先が壊れる変更');
    expect(drift).toContain('reference.queryKeys.text');
  });

  it('calls a removed vocabulary word breaking', () => {
    const before = changed((surface) => {
      surface.vocabulary.state = [...surface.vocabulary.state, 'archived'];
    });

    const drift = surfaceDrift(before, current);

    expect(drift).toContain('渡した先が壊れる変更');
    expect(drift).toContain('"archived" が無くなった');
  });

  it('calls a word appended to the end compatible', () => {
    const before = changed((surface) => {
      surface.vocabulary.state = surface.vocabulary.state.slice(0, -1);
    });

    const drift = surfaceDrift(before, current);

    expect(drift).toContain('互換の変更');
    expect(drift).not.toContain('渡した先が壊れる変更');
  });

  it('calls a reordered list breaking, because a reader may read columns by position', () => {
    const before = changed((surface) => {
      surface.export.assetFields = [...surface.export.assetFields].reverse();
    });

    const drift = surfaceDrift(before, current);

    expect(drift).toContain('渡した先が壊れる変更');
    expect(drift).toContain('並びが変わった');
  });

  it('calls a new key compatible and a dropped key breaking, in the same report', () => {
    const before = changed((surface) => {
      delete (surface.reference as Record<string, unknown>)['dateFormat'];
      (surface.export as Record<string, unknown>)['charset'] = 'utf-8';
    });

    const drift = surfaceDrift(before, current);

    expect(drift).toContain('reference.dateFormat: 増えた');
    expect(drift).toContain('export.charset: 無くなった');
  });

  it('prints the current surface, so the committed file can be corrected', () => {
    const before = changed((surface) => {
      surface.export.version = 0;
    });

    expect(surfaceDrift(before, current)).toContain(JSON.stringify(current, null, 2));
  });

  it('says so when it cannot name the difference rather than reporting nothing', () => {
    // 鍵も値も並びも同じで、順序だけが違う。比較は名前を付けられない。
    const reordered = {...current, vocabulary: current.vocabulary, reference: current.reference};
    const shuffled = JSON.parse(
      JSON.stringify({
        export: reordered.export,
        reference: reordered.reference,
        vocabulary: reordered.vocabulary,
      })
    ) as ReturnType<typeof catalogSurface>;

    const drift = surfaceDrift(shuffled, current);

    expect(drift).toContain('比較が読まないどこかが動いている');
  });
});
