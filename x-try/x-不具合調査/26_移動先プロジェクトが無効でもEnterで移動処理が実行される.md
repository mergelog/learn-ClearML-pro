# 移動先プロジェクトが無効でも、Enter で移動処理が実行される

| 項目 | 内容 |
|---|---|
| カテゴリー | 処理値 |
| 不具合内容 | タスク・モデル・レポート・プロジェクトの「Move to project」ダイアログでは、画面の MOVE ボタンが無効な移動先を Enter で確定できる。フォームの submit ハンドラが検証結果を確認せず、移動処理またはダイアログの確定を呼ぶためである |
| 期待動作 | 無効な移動先（空、空白だけ、現在のプロジェクト、重複または禁止されたパス）は Enter でも確定・移動できない |
| 直さないと困ること | クリック操作では防いでいる不正な移動をキーボード操作だけで実行できる。空または不正なプロジェクト ID を含む要求が API に渡り、利用者には操作不能・意図しない移動・エラー通知として現れる |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験・モデル・レポートの「MOVE TO PROJECT」、プロジェクトの移動ダイアログ |
| 観点 | G（フォームと検証） |
| 重大度 | S2 |
| 確度 | コード上確定 |
| 由来 | 上流 |
| 発生条件 | 移動先の入力欄にフォーカスがある状態で、移動先が無効なまま Enter を押す |
| 関連 | [04](./04_インライン編集の通常のEnterで保存処理が2回走る.md)（フォームの暗黙送信）、[06](./06_実験名の長さの下限が入力欄と保存処理で食い違う.md)（表示上の検証と保存処理の不一致） |

## 症状

通常のクリックでは MOVE ボタンが `moveProjectForm.invalid` または `moveToForm.invalid` のとき無効になる。しかし Enter による submit はボタンの click を通らず、次の2つの submit ハンドラを直接実行する。

| 画面 | 通常クリック | Enter の submit | 結果 |
|---|---|---|---|
| タスク・モデル・レポートの移動 | MOVE は `moveProjectForm.invalid` で無効 | `closeDialog()` を無条件で呼ぶ | 無効値でもダイアログが `{name, id: ''}` または選択済みの値として閉じ、呼び出し元が移動 action を dispatch する |
| プロジェクトの移動 | MOVE は `moveToForm.invalid` で無効 | `send()` を無条件で呼ぶ | 無効な destination を含む `moveProject` output が発火する |

## 再現手順

1. タスク、モデル、またはレポートのメニューから **MOVE TO PROJECT** を開く
2. 移動先を空白だけ、現在のプロジェクト、または検証エラーになるプロジェクト名にする
3. MOVE ボタンが無効であることを確認する
4. 入力欄にフォーカスを戻して Enter を押す
5. 本来は無効な値でもダイアログが確定し、移動処理が進む

プロジェクトの移動でも同様に、無効な移動先を入力して Enter を押すと `moveProject` output が発火する。

## 原因

タスク・モデル・レポートが共有するダイアログでは、フォーム自身に `(submit)="closeDialog()"` があり、`closeDialog()` 内にも `moveProjectForm.valid` の判定がない。

```html
<form (submit)="closeDialog()" [formGroup]="moveProjectForm">
  <!-- 移動先入力 -->
</form>
<button [disabled]="moveProjectForm.invalid" (click)="closeDialog()">MOVE</button>
```

([move-project-dialog.component.html:14](../src/app/webapp-common/experiments/shared/components/move-project-dialog/move-project-dialog.component.html#L14)、[同:58](../src/app/webapp-common/experiments/shared/components/move-project-dialog/move-project-dialog.component.html#L58)、[move-project-dialog.component.ts:118](../src/app/webapp-common/experiments/shared/components/move-project-dialog/move-project-dialog.component.ts#L118))

プロジェクト専用のフォームも `(submit)="send()"` に対して `send()` が `moveToForm().valid` を確認しない。同フォームの MOVE ボタンは無効化しているため、クリックと Enter の結果が食い違う。

([project-move-to-form.component.html:13](../src/app/webapp-common/shared/project-dialog/project-move-to-form/project-move-to-form.component.html#L13)、[同:56](../src/app/webapp-common/shared/project-dialog/project-move-to-form/project-move-to-form.component.html#L56)、[project-move-to-form.component.ts:113](../src/app/webapp-common/shared/project-dialog/project-move-to-form/project-move-to-form.component.ts#L113))

フォームの submit は、フォーム外に置かれた無効な MOVE ボタンの `disabled` を通らない。`FormGroupDirective` / `NgForm` が既定動作のページ遷移を止めても、テンプレートに書かれた submit 式は実行される。

## 影響範囲と同種箇所

- `MoveProjectDialogComponent` は実験の右クリックメニュー、モデルのメニュー、レポートの Effect から共用される
- `ProjectMoveToFormComponent` はプロジェクトの移動ダイアログで使われる
- `select-queue` は submit 式自体が `queueControl.valid && closeDialog(true)` であり、同じ問題はない
- 作成・編集フォームの多くは submit を持たず、無効な主ボタンがフォーム外にあるため、Enter で保存を実行しない

## 対策案

submit を検証の唯一の入口にする。例えば共有ダイアログは `(ngSubmit)="moveProjectForm.valid && closeDialog()"`、プロジェクトの移動は `(ngSubmit)="moveToForm.valid && send()"` とする。MOVE ボタンは `type="submit"` を明示し、click ハンドラを外す。

防御を二重化するなら、`closeDialog()` と `send()` の先頭でも valid を確認する。テンプレートだけの修正より堅く、将来ほかの呼び出し方を足しても無効値を処理しない。

## 検証範囲

- 確認したこと：対象外を除く34個の `<form>` を列挙し、`(submit)`・主ボタンの `disabled`・保存/移動メソッドを照合した。上記2系統は、submit と主ボタンで検証の有無が食い違うことをコードで確認した
- 確認していないこと：実バックエンドで無効な移動要求を送ること。調査用データへの書き込みを避けたため、画面上の最終的な API 応答は未確認である
- 由来：`move-project-dialog` と `project-move-to-form` は比較資料で上流と一致する
