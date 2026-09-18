---
name: ngbi
description: bulletin スキルの別名。「/ngbi {処理内容}」で Bulletin解析 (ngbi-*.md) を作成する。`--code` も bulletin と同じく使える。
argument-hint: "[処理内容] [--code]"
disable-model-invocation: true
---

# ngbi（bulletin の別名）

引数: $ARGUMENTS

Skill ツールで `bulletin` スキルを、上記の引数をそのまま（`--code` を含めて）渡して呼び出し、その指示どおりに Bulletin解析を作成する。
Skill ツールが使えない場合は [../bulletin/SKILL.md](../bulletin/SKILL.md) を読んで同じ手順に従う。

処理内容が空の場合は、作成せずに追跡したい処理内容をユーザに確認する。
