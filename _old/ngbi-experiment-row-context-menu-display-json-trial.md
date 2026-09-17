# Bulletin JSON Trial: 実験一覧の右クリックメニュー表示

実装を上から順番に開いて追うため、振る舞いをJSON配列として表現した試作版。

見た目をJSONへ寄せつつソースを開けるように、`link` と `links` の値だけクリック可能にしている。

<pre>
[
  {
    "hr": "------------------------------------------------",
    "index": 0,
    "name": "行の右クリックを検出",
    "trigger": {
      "source": "ユーザー",
      "event": "実験一覧の行を右クリック",
      "connection": "行の pContextMenuRow が対象の rowData をPrimeNGへ登録"
    },
    "implementation": {
      "component": "TableComponent",
      "locations": [
        {
          "symbol": "pContextMenuRow",
          "link": <a href="./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L124">"src/app/webapp-common/shared/ui-components/data/table/table.component.html#L124"</a>
        },
        {
          "symbol": "onContextMenuSelect",
          "link": <a href="./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L36">"src/app/webapp-common/shared/ui-components/data/table/table.component.html#L36"</a>
        }
      ]
    },
    "componentOverview": {
      "display": "各一覧画面で再利用される共通テーブル",
      "receivesFrom": "ExperimentsTableComponent",
      "receives": ["実験の行データ", "列定義", "選択状態"],
      "returnsTo": "ExperimentsTableComponent",
      "returns": "rowRightClick"
    },
    "process": {
      "technologies": ["PrimeNG p-table", "pContextMenuRow", "onContextMenuSelect"],
      "code": "(onContextMenuSelect)=\"openContext($event)\"",
      "description": "PrimeNGが右クリックされた行とMouseEventを特定し、openContext()を呼ぶ",
      "note": "p-context-menuはd-none。表示ではなくイベント検出に使用"
    },
    "effects": [
      {
        "name": "TableComponent.openContext()を実行",
        "visibleChange": false
      }
    ]
  },
  {
    "hr": "------------------------------------------------",
    "index": 1,
    "name": "右クリック情報を実験テーブルへ返す",
    "trigger": {
      "sourceIndex": 0,
      "source": "TableComponent template",
      "event": "onContextMenuSelect",
      "connection": "テンプレートからopenContext($event)を直接呼び出す"
    },
    "implementation": {
      "component": "TableComponent",
      "method": "openContext",
      "links": [
        <a href="./src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L421">"src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L421"</a>,
        <a href="./src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L174">"src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L174"</a>,
        <a href="./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L31">"src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L31"</a>
      ]
    },
    "componentOverview": {
      "display": "共通テーブル",
      "roleHere": "PrimeNGイベントをアプリ用イベントへ変換する中継点",
      "receivesFrom": "PrimeNG",
      "receives": ["originalEvent", "rowData", "single"],
      "returnsTo": "ExperimentsTableComponent",
      "returns": "rowRightClick"
    },
    "process": {
      "technologies": ["Angular EventEmitter", "@Output"],
      "code": "rowRightClick.emit({e: originalEvent, rowData: data, single})",
      "description": "PrimeNG固有のイベントをアプリ側が扱う形式へ変換してemit",
      "cleanup": [
        "PrimeNGのcontextMenuSelectionをnullへ戻す",
        "非表示のp-context-menuを閉じる"
      ]
    },
    "effects": [
      { "name": "右クリック処理の担当が共通テーブルから実験テーブルへ移る" }
    ]
  },
  {
    "hr": "------------------------------------------------",
    "index": 2,
    "name": "対象実験と表示座標を確定",
    "trigger": {
      "sourceIndex": 1,
      "source": "TableComponent.openContext()",
      "event": "rowRightClick",
      "connection": "(rowRightClick)=\"openContextMenu($event)\""
    },
    "implementation": {
      "component": "ExperimentsTableComponent",
      "method": "openContextMenu",
      "links": [
        <a href="./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L349">"src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L349"</a>,
        <a href="./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L197">"src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L197"</a>,
        <a href="./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L165">"src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L165"</a>
      ]
    },
    "componentOverview": {
      "display": "実験固有の一覧、セル、選択状態、カード表示",
      "receivesFrom": "ExperimentsComponent",
      "receives": ["experiments", "checkedExperiments", "tableCols"],
      "returnsTo": "ExperimentsComponent",
      "returns": ["contextMenu", "experimentsSelectionChanged"]
    },
    "process": {
      "technologies": ["Angular signal", "Angular output", "MouseEvent"],
      "steps": [
        "右クリックされた実験をcontextExperimentへ保存",
        "必要ならチェック対象を右クリックした1件へ変更",
        "preventDefault()でブラウザ標準メニューを抑止",
        "clientXとclientYをcontextMenu outputで親へ通知"
      ],
      "selectionBranch": {
        "checkedRow": "現在の複数選択を維持",
        "uncheckedRow": "選択を右クリックした1件へ変更"
      },
      "outputCode": "contextMenu.emit({x: event.clientX, y: event.clientY, single, backdrop})"
    },
    "effects": [
      { "name": "メニュー操作の対象実験が決まる" },
      {
        "name": "未チェック行の場合はチェック状態も変わる",
        "conditional": true
      },
      { "name": "親Componentへ右クリック位置が通知される" }
    ]
  },
  {
    "hr": "------------------------------------------------",
    "index": 3,
    "name": "表示対象のメニューComponentを呼ぶ",
    "trigger": {
      "sourceIndex": 2,
      "source": "ExperimentsTableComponent.openContextMenu()",
      "event": "contextMenu",
      "connection": "(contextMenu)=\"onContextMenuOpen($event)\""
    },
    "implementation": {
      "component": "ExperimentsComponent",
      "method": "onContextMenuOpen",
      "links": [
        <a href="./src/app/webapp-common/experiments/experiments.component.html#L111">"src/app/webapp-common/experiments/experiments.component.html#L111"</a>,
        <a href="./src/app/webapp-common/experiments/experiments.component.ts#L735">"src/app/webapp-common/experiments/experiments.component.ts#L735"</a>,
        <a href="./src/app/webapp-common/experiments/experiments.component.ts#L240">"src/app/webapp-common/experiments/experiments.component.ts#L240"</a>
      ]
    },
    "componentOverview": {
      "display": "検索、一覧、詳細、フッター、メニューを束ねる実験管理画面",
      "receivesFrom": ["NgRx Store", "ExperimentsTableComponent"],
      "receives": ["実験状態", "右クリック座標", "単一行フラグ", "backdropフラグ"],
      "returnsTo": "ExperimentMenuExtendedComponent",
      "returns": "outputではなくopenMenu()を直接呼び出す"
    },
    "process": {
      "technologies": ["viewChild.required", "computed", "Component継承"],
      "steps": [
        "singleRowContextを更新",
        "menuBackdropを更新",
        "contextMenu()から子のメニューComponent参照を取得",
        "openMenu({x, y})を呼ぶ"
      ],
      "code": "this.contextMenu().openMenu({x, y})"
    },
    "precondition": {
      "description": "右クリック前にメニューComponentがビュー内へ描画されている",
      "path": [
        "contextMenuExtendedTemplateを定義",
        "contextMenuTemplate inputで子へ渡す",
        "ngTemplateOutletで描画"
      ],
      "links": [
        <a href="./src/app/webapp-common/experiments/experiments.component.html#L140">"src/app/webapp-common/experiments/experiments.component.html#L140"</a>,
        <a href="./src/app/webapp-common/experiments/experiments.component.html#L94">"src/app/webapp-common/experiments/experiments.component.html#L94"</a>,
        <a href="./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L1">"src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L1"</a>
      ]
    },
    "effects": [
      { "name": "イベントによる通知から子Componentへのメソッド呼び出しへ移る" },
      { "name": "単一行モードとbackdropの有無が確定する" }
    ]
  },
  {
    "hr": "------------------------------------------------",
    "index": 4,
    "name": "非表示トリガーを右クリック位置へ移動",
    "trigger": {
      "sourceIndex": 3,
      "source": "ExperimentsComponent.onContextMenuOpen()",
      "event": "openMenu({x, y})の直接呼び出し",
      "connection": "ExperimentMenuComponentがBaseContextMenuComponentを継承"
    },
    "implementation": {
      "component": "BaseContextMenuComponent",
      "method": "openMenu",
      "links": [
        <a href="./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L48">"src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L48"</a>,
        <a href="./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L36">"src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L36"</a>,
        <a href="./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11">"src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11"</a>
      ]
    },
    "componentOverview": {
      "display": "自身は表示を持たないコンテキストメニュー共通基底Component",
      "receivesFrom": "ExperimentsComponent",
      "receives": "右クリック座標{x, y}",
      "returnsTo": "ExperimentsComponent",
      "returns": ["menuOpened", "menuClosed"]
    },
    "process": {
      "technologies": ["Angular signal", "viewChild(MatMenuTrigger)", "CSS position: fixed"],
      "steps": [
        "既存メニューが開いていれば閉じる",
        "position Signalへ{x, y}を設定",
        "非表示トリガーのleftとtopへ座標を反映",
        "座標反映を待つため100ms後に表示処理へ進む"
      ],
      "positionPath": "MouseEvent.clientX/clientY → position Signal → hidden trigger left/top"
    },
    "effects": [
      { "name": "Angular Materialが位置計算に使う基準点が右クリック位置へ移る" },
      {
        "name": "トリガー自体はvisibility:hiddenのため見えない",
        "visibleChange": false
      }
    ]
  },
  {
    "hr": "------------------------------------------------",
    "index": 5,
    "name": "Angular Materialのメニューを表示",
    "trigger": {
      "sourceIndex": 4,
      "source": "BaseContextMenuComponent.openMenu()",
      "event": "100ms後のコールバック",
      "connection": "非表示トリガーのmatMenuTriggerForがexperimentMenuを参照"
    },
    "implementation": {
      "component": "BaseContextMenuComponent / ExperimentMenuComponent",
      "method": "MatMenuTrigger.updatePosition / openMenu",
      "links": [
        <a href="./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L54">"src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L54"</a>,
        <a href="./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11">"src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11"</a>,
        <a href="./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L18">"src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L18"</a>
      ]
    },
    "componentOverview": {
      "display": "詳細、キュー操作、共有、削除、アーカイブなどの実験操作メニュー",
      "receivesFrom": "ExperimentsComponent",
      "receives": ["対象実験", "選択実験", "各操作の可否"],
      "returnsTo": "ExperimentsComponent",
      "returns": ["menuOpened", "menuClosed", "タグ操作イベント"]
    },
    "process": {
      "technologies": ["Angular Material MatMenuTrigger", "mat-menu", "Angular CDK Overlay"],
      "steps": [
        "updatePosition()で移動後のトリガーを基準に位置を再計算",
        "openMenu()でexperimentMenuをOverlayへ表示",
        "menuOpened.emit()で表示状態を親へ通知"
      ]
    },
    "effects": [
      {
        "name": "実験のコンテキストメニューが右クリック位置へ表示される",
        "visibleChange": true
      },
      { "name": "contextMenuActiveがtrueになり、対象行のハイライトが維持される" }
    ],
    "bulletinEnd": "メニュー表示へ到達。メニュー項目クリック後は対象外"
  }
]
</pre>
