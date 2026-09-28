
html/
├── head
└── body
    └── sm-root
        └── sm-app-shell
            ├── sm-update-notifier
            ├── sm-color-picker-wrapper [ns]
            │   └── sm-side-nav/ [ns]
            │       └── a: data-id="modelEndpointsIcon"
            └── sm-header
                └── sm-breadcrumbs
                    └── button: data-id="globalSearchButton" in mat

のような階層表現を追加する
記載は、作成するhtmlの最上部にコメントアウトで記載する
<!--
ここに記載
-->

対象タグは
- mat-* 以外のタグ名にハイフンがつくもの
- data-idの指定があるもの。data-idも記入
- 上記のうちタグにハイフンがつかないもので、ハイフンタグ以降から換算して mat- タグの配下にある場合、末尾に in mat を付与する
  
さらに
sm-* のタグは selector: 'sm-*', 
で検索してコンポーネントが存在しなければ 末尾に [ns]を書く

