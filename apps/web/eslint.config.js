// @ts-check
const eslint = require("@eslint/js");
const tseslint = require("typescript-eslint");
const angular = require("angular-eslint");
const ngrx = require("@ngrx/eslint-plugin");

module.exports = tseslint.config(
  {
    // ignores だけを持つ設定オブジェクトが、flat config 全体の除外になる。
    // 旧 .eslintignore の内容に、生成物と Stryker の一時サンドボックスを加えた。
    // .stryker-tmp はソースの写しなので、含めると同じ違反を二重に数えてしまう。
    ignores: [
      ".angular/**",
      ".stryker-tmp/**",
      "build/**",
      "dist/**",
      "e2e/**",
      "electron/**",
      "node-sass/**",
      "node_modules/**",
      "playwright-report/**",
      "stories/**",
      "test-results/**",
    ],
  },
  {
    files: ["**/*.ts"],
    extends: [
      eslint.configs.recommended,
      ...tseslint.configs.recommended,
      ...tseslint.configs.stylistic,
      ...angular.configs.tsRecommended,
      // NgRx を全面採用しているのに、これまでプラグイン自体が未登録だった。
      // ESLint 9 以降は未登録プラグインのルールも "off" ならエラーにならないため、
      // 下の "off" 1行だけが書かれた状態で全ルールが黙って無視されていた。
      // 型情報を要求しない `all` を使う（この設定は型付き lint を構成していない）。
      ...ngrx.configs.all,
    ],
    processor: angular.processInlineTemplates,
    rules: {
        "no-console": "error",
        "no-debugger": "error",
        "quotes": ["error", "single", {
          "allowTemplateLiterals": true
        }],
        "@angular-eslint/directive-selector": [
          "error",
          {
            "type": "attribute",
            "prefix": "sm",
            "style": "camelCase"
          }
        ],
        "@angular-eslint/component-selector": [
          "error",
          {
            "type": "element",
            "prefix": "sm",
            "style": "kebab-case"
          }
        ],
        // Angular 22 では OnPush が既定なので、このルールが咎めるのは
        // `ChangeDetectionStrategy.Default`（= Eager）への明示的な離脱だけである。
        // 離脱するなら理由が要る、という形にしておく。
        "@angular-eslint/prefer-on-push-component-change-detection": "error",
        // 唯一の意図的な無効化。observable を直接返す書き方は全域で使われており、
        // 264件（うち自作 quality-pipeline 7件）を機械整形するだけの価値が無い。
        // 以前もこの1行だけが書かれていたが、プラグイン未登録のため効いていなかった。
        // 接続した今は「意図して切っている」という意味を持つ。
        "@ngrx/prefer-effect-callback-in-block-statement": "off"
    },
  },
  {
    files: ["**/*.html"],
    extends: [
      ...angular.configs.templateRecommended,
      ...angular.configs.templateAccessibility,
    ],
    rules: {
      // use-track-by-function は *ngFor 用で、旧制御フローが0の本リポジトリでは
      // 意味を持たない（@for は track が構文上必須）。0のうちにゲートを立てる。
      "@angular-eslint/template/prefer-control-flow": "error",
      "@angular-eslint/template/no-any": "error",
      "@angular-eslint/template/prefer-self-closing-tags": "warn"
    },
  }
);
