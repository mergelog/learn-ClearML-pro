import {expect, test} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

/**
 * フェーズ2 観点C（フェーズ0から回した候補）：Tip of the day（src/onboarding.json）の画像と本文。
 * - onboarding.json が指す画像（ライトテーマでは `-light` を付けた名前）が開発サーバで取得できるか
 * - 本文の `<br/<<br/>` が、[innerHTML] でどう描画されるか
 */
const tips: {image?: string; content: string}[] = JSON.parse(readFileSync(resolve('src/onboarding.json'), 'utf8')).onboarding;

test('Tip of the day の画像の取得結果', async ({request}) => {
  const images = [...new Set(tips.map(t => t.image).filter(Boolean) as string[])];
  const results: Record<string, number> = {};
  for (const image of images) {
    const light = image.replace(/\.svg$/, '-light.svg');
    for (const path of [image, light, `app/webapp-common/${image.replace('assets/', 'assets/icons/')}`]) {
      results[path] = (await request.get(`/${path}`)).status();
    }
  }
  console.log(JSON.stringify(results, null, 1));
  expect(results['assets/welcome-researcher.svg']).toBe(404);
});

test('本文の `<br/<<br/>` の描画', async ({page}) => {
  const tip = tips.find(t => t.content.includes('<br/<<br/>'))!;
  await page.setContent('<div id="tip"></div>');
  const result = await page.evaluate(content => {
    const div = document.getElementById('tip')!;
    div.innerHTML = content;
    return {html: div.innerHTML, text: div.innerText};
  }, tip.content);
  console.log(JSON.stringify(result, null, 1));
});
