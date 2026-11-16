# CLAUDE.md

## 本番ページ
- **本番（授業で実際に使うページ）は `public/index_conditions_forclass.html`**。`public/index.html` ではない。
  テスト・修正・deploy・動作確認は、特に指定がなければこのファイルを対象にする。
- 保存先は Firebase Realtime Database の `post_class`（プロジェクト `restaurant-79715`）。
- 公開先は Firebase Hosting（https://restaurant-79715.web.app/index_conditions_forclass.html）。
  deploy: `firebase deploy --only hosting --project restaurant-79715`（設定は `firebase.json` / `.firebaserc`）。
- フィードバック条件は `?cond=self|self_best|full` で固定できる（指定なしはランダム）。

## テスト
- E2E: `.venv/bin/python -m pytest tests`（Playwright・headless・Firebase はスタブで本番に書き込まない）。
- 本番 DB（`post_class`）への書き込みを伴う実行は、ユーザーの許可を得てから行う。
  テストで作ったノードは本番データなので、削除はユーザーがコンソールで行う（Claude は削除しない）。
- DB の読み取りはルールで拒否されるため、中身の確認は Firebase コンソール（claude-in-chrome）で行う。

## 作業ルール
- 実行（テスト・E2E など）はブランチを切ってから行う。
- 実 Chrome（claude-in-chrome）では SurveyJS のスライダーは実キー入力でしか値が入らない。
  また jsPsych の画面遷移は非同期なので、画面固有の要素（例 `.choose-msg`）を待ってから操作する。
