/**
 * 推論サービスの負荷試験（k6）。
 *
 * 答えるのは1つだけである。**配備された `prediction_api` が、決めた期限の
 * 内側で答え続けるか。** 期限はこの試験のために新しく決めたものではなく、
 * 運用が既に鳴らすと決めている値（`infra/observability/alerts.yml`）を
 * そのまま使う。
 *
 *   - 95パーセンタイルが 1 秒を超えない（PredictionLatencyHigh）
 *   - サービス側の失敗が 5% を超えない（PredictionErrorRateHigh）
 *
 * 別の数字をここで決めると、「試験は緑なのに本番は鳴る」あるいはその逆が
 * 起きる。どちらも**宣言と実態のずれ**であり、ずれたという理由では表に
 * 出てこない。2つが同じ値であることは `scripts/tests/perf-thresholds.test.mjs`
 * が見ている。
 *
 * 見ないこと:
 *   - モデルの精度（ml の単体テストと評価の範囲）
 *   - ClearML Server の性能（推論の応答はモデル読み込み後、Serverを見ない）
 *   - 長時間の耐久・スケール（数分の試験で分かるのは「いま答えられるか」だけ）
 *
 * 走らせ方は `pnpm run serving:load`（`scripts/load-test.sh`）。
 * backend と推論サービスが起動している必要があるため、`verify` にも CI にも
 * 載せていない。判断は runbook 004 と 00_プラン §5.1.10 にある。
 */

import http from 'k6/http';
import {check} from 'k6';

/** 運用のしきい値。alerts.yml と同じ値であること。 */
const LATENCY_BUDGET_MS = 1000;
const ERROR_BUDGET_RATE = 0.05;

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8090';
const TOKEN = __ENV.PREDICTOR_TOKEN || '';
const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || '30s';
/** 1回の要求に載せる測定の数。工程の1ロット分を1回で尋ねる想定。 */
const BATCH_SIZE = Number(__ENV.BATCH_SIZE || 10);

export const options = {
  scenarios: {
    predict: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
    },
  },
  thresholds: {
    // 期限を超えた時点で失敗にする。超えてから報告を読む形にすると、
    // 「遅いが緑」という結果が残る。
    http_req_duration: [`p(95)<${LATENCY_BUDGET_MS}`],
    http_req_failed: [`rate<${ERROR_BUDGET_RATE}`],
    // 形の壊れた応答は速くても失敗である。
    checks: ['rate==1.00'],
  },
};

/**
 * 1回分の測定。値は `scripts/serving-smoke.sh` が送るものと同じ範囲にする。
 *
 * 乱数で作るのは、同じ値を送り続けると前処理や分岐の一部しか通らないため
 * である。分布そのものを再現する試験ではない。
 */
function measurement(index) {
  return {
    sample_id: `LOAD-${String(index).padStart(5, '0')}`,
    equipment_id: 'EQ-01',
    process_step: 'ETCH',
    temperature: 410 + Math.random() * 10,
    pressure: 12 + Math.random(),
    process_time: 55 + Math.random() * 10,
    gas_flow: 30 + Math.random() * 5,
    sensor_1: Math.random() - 0.5,
    sensor_2: Math.random() - 0.5,
    inspection_value: 8 + Math.random() * 2,
  };
}

export function setup() {
  if (!TOKEN) {
    // 資格情報が無いと 401 だけが返り、速いまま全部失敗する。
    // 「負荷を掛けられなかった」ことを負荷の結果として読ませない。
    throw new Error('PREDICTOR_TOKEN is not set. Run through scripts/load-test.sh.');
  }

  const ready = http.get(`${BASE_URL}/ready`, {
    headers: {Authorization: `Bearer ${TOKEN}`},
  });

  if (ready.status !== 200) {
    throw new Error(`${BASE_URL}/ready answered ${ready.status}, not 200. Nothing to measure.`);
  }

  return {modelVersion: ready.json('model.model_version')};
}

export default function (data) {
  const measurements = [];
  for (let index = 0; index < BATCH_SIZE; index += 1) {
    measurements.push(measurement(__ITER * BATCH_SIZE + index));
  }

  const response = http.post(
    `${BASE_URL}/predict`,
    JSON.stringify({measurements}),
    {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        'Content-Type': 'application/json',
      },
      tags: {endpoint: 'predict'},
    }
  );

  check(response, {
    'answers 200': (answer) => answer.status === 200,
    'answers about every measurement': (answer) =>
      answer.status === 200 && answer.json('predictions').length === BATCH_SIZE,
    // 走っている間にモデルが入れ替わったなら、前半と後半は別のものを測っている。
    'answers with the model it started with': (answer) =>
      answer.status === 200 && answer.json('model.model_version') === data.modelVersion,
  });
}
