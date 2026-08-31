# WuWa Inventory Kamera — 開発メモ (Claude 向け)

鳴潮 (Wuthering Waves) の手持ちデータを画面OCRでJSON化するツール。
Psycho-Marcus/WuWa_Inventory_Kamera のフォークで、本家は 2025-09 から停止
(Issue 半年放置)。このフォークが実質的な本流。ライセンスは GPL-3.0。

## このフォークで変えたこと(要点)

- ウィンドウモード対応: キャプチャ/クリック座標をクライアント領域原点基準に
  (`WindowManager.getClientArea()` → `ScreenInfo.originX/originY`)。フルスクリーン
  でなくてもスキャン可能
- 日本語対応: ウィンドウタイトル「鳴潮」検出、日本語OCRモデル
  (ModelScope の PP-OCRv4 japan を `properties/config.py` の `_createOCR` が自動DL)
- 3.6 UI 対応: characters 系 ROI を全面再採寸。スキルはツリー画面の帯OCR
  (クリック不要)、チェーンはノードのシアン発光をHSVピクセル判定
- キャラ/武器DBを nanoka.cc (旧 hakush.in) から再構築
  (`updater/databaseUpdater.py: updateFromNanoka`)
- ロースター巡回: 少量スクロール+重複スキップ+「2連続空パスで終了」方式
  (スクロール量の不正確さに耐性)

## 環境(このマシン)

- Windows 11 / モニタ1枚 5120x2160 / ゲームは通常ウィンドウ 2560x1440・日本語
- venv: `.venv` (Python 3.13, Windows側)。実行はWindows必須 (win32/mss/PySide6)
- GUI起動: `管理者として起動(ソース版).bat` (管理者必須 — ゲームが昇格プロセスで、
  キー送出に昇格が要る)
- CLIスキャン: `scan_cli.py`。タスクスケジューラ `WuWaKameraScan` (最上位権限) を
  `スキャンタスク登録.bat` で一度登録すれば、以後 `schtasks /run /tn WuWaKameraScan`
  でUACなしに実行できる。結果は `scan_cli_out.txt`
- 出力先: `C:/Users/air_d/Documents/wuwa/kamera_export`(config/config.json)。
  `..\copy_latest_scan.ps1` が最新結果を `Documents\wuwa` 直下へ簡易名でコピー

## Git 運用

- push は WSL 側の git/gh を使う (Mekajiki, SSH認証済み)。WSL 側は
  `core.autocrlf=true` 設定済み。Windows 側 git でコミットすると CRLF で全行差分
  になるので使わない
- GitHub API を叩くときも WSL の `gh api`(認証済みでレート制限に余裕)。
  素の HTTP は 60回/時で枯渇しやすい

## OCR の知見 (rapidocr 3.x + PP-OCRv5)

- rapidocr 3.9.2、det=PP-OCRv5 mobile / rec=PP-OCRv5 **ch server**
  (v5のchモデルは日本語かな込みで公式カバー、精度はv4 japan mobileより大幅に上。
  韓国語のみ korean rec を使う)。モデルは初回に site-packages/rapidocr/models へ自動DL
- **`ocr(img, use_det=..)` のオプションはインスタンスに残留する**
  (update_params が保存される)→ 全呼び出しで use_det/use_cls/use_rec を明示必須
- 小さい入力は自動でdetスキップされ boxes 無しの結果が返る → `_resultPairs` で正規化
- **v5はカタカナを同形漢字に読む癖**(ニ→二、エ→工、カ→力、ト→卜等)→
  照合時に `KANA_LOOKALIKES` 正規化バリアントも試す
- **白黒二値化はv5には逆効果**(自然画像で学習)→ OCRはカラー crop、
  ハッシュ(重複検出)だけ二値化画像で取る
- det は端に接した文字を落とす → 10pxパディング(`_prepare`)
- 単行フィールド(名前等)は `recognizeLine()`(rec直行)、
  フォントサイズ混在の行(Lv 90/90)は det 経由の `imageToString` が安定
- 全角数字/記号/中黒(・と·)は `FULLWIDTH_TABLE` で正規化
- スラッシュ欠落対策: `splitLevel()`、小数点カンマ誤読対策: `normalizeValue()`
- 照合の多段構え: エイリアス表(exact→fuzzy0.8) → 完全一致 → fuzzy →
  一意部分一致 → 一意前方一致。誤読変種は基本これで吸収され、
  nameAliases.json への追記が必要なケースは稀になった

## 名前照合

- `matchName()`: エイリアス表 → 完全一致 → 曖昧一致(段階cutoff) → 一意部分一致。
  '-'→'ー' 正規化あり
- 漢字の見間違い (秧秧→秋秋) は編集距離ゼロなので **`nameAliases.json`** で吸収。
  読めなかった/照合できなかった名前はクロップが `logs/fail/name_*.png` に残る
  → 目視で正体確認 → エイリアス追記、が保守フロー

## データソース

- nanoka.cc: `https://static.nanoka.cc/manifest.json` → `ww.latest` (例 "3.6+365"、
  パスには '+' 前の "3.6" を使う) → `https://static.nanoka.cc/ww/{ver}/{table}.json`
  (character / weapon / echo / item など)。**User-Agent 必須** (既定UAは403)
- Dimbreath/WutheringData は 3.1 (2026-03) で停止。MultiText 由来の派生
  (definedText, echoStats, sonataName, achievements, echoes) はまだそこ依存 →
  echoes/items を触るときは nanoka へ移行すること

## 採寸・検証ワークフロー (UI変更時の保守手順)

1. ゲーム側を対象画面にして撮影: `画面撮影.bat` (単発) /
   `セクション撮影.bat` (共鳴者画面の全セクション自動巡回) /
   `追加撮影.bat` (ポップアップ系)
2. スクショから OCR ボックス座標をダンプして実座標を得る (validate3.py 方式:
   `ocr(crop)` の bbox を 1080p 換算で出す)。目測より正確
3. `game/gameROI.py` の 1920x1080 基準テーブルを更新 (他解像度は同アスペクト比
   なら線形スケールされる)
4. **実機再スキャンの前にオフライン検証**: validate4.py 方式で保存スクショに対して
   実際のスクレイパー関数を呼び、期待値と突き合わせる
5. 実機スキャン → `dump_result.py <characters json>` で一覧確認

## ハマりどころ

- Windows はディスプレイモード変更で `\\.\DISPLAYn` を振り直す → mss の
  インデックス範囲外になる (クランプ実装済み)
- スキャン監視 (needToStop) はフォーカスが1秒外れると子プロセスを殺す。
  RDP越しはレンダリング停止や解像度変化で誤爆するため非推奨
- 子プロセス (multiprocessing spawn) は親のログ設定を継がない →
  `logs/scraper.debug.log` に basicConfig 済み。例外はここを見る
- .ps1 は Windows PowerShell 5.1 だと UTF-8(BOMなし) の日本語で構文崩壊する
  → ps1 は ASCII のみで書く
- bat から昇格起動するとき `%~dp0` の末尾 `\` が引用符を壊す → `"%~dp0."`
- ユーザーは鳴潮3.6の言語移行版(C#化)限定テスト対象 (バージョンに「*」)。
  ゲーム側の挙動変化はこの影響も疑うこと

## バックログ: 差分スキャン(設計済み・未実装、優先度低)

時間を食うのは装備音骸の詳細クリック(~20s/キャラ)のみ。ステータス画面
左パネルの実測合計値(HP/攻撃/防御/共鳴効率/クリ率/クリダメ)は音骸・武器の
変更を必ず反映するので、これを毎回OCRして出力に含め(育成計画の答え合わせ
にも有用)、前回スキャンと一致したキャラは音骸詳細をスキップして前回値を
流用する。スキル/チェーンはクリック不要なので毎回読む。20分→8分程度の見込み。

## 残タスク / ロードマップ

1. **音骸スキャン (Bメニュー) の 3.6 対応** — ユーザーの本目的
   (育成計画立案) に必須。echoes DB の nanoka 移行も込み
2. 素材/武器インベントリ (Bメニュー) の 3.6 対応
3. **フルスクリーン (5120x2160, 21:9) 対応** — 16:9 テーブルから
   「高さ基準スケール+左右端アンカー」で座標を導出する方式を検証中
4. 完成後: 本家に告知Issue → 反応なければフォークで GitHub Releases
   (cx_Freeze ビルド、本家の仕組み流用)

## 秧秧(1402)のスキルが読めない既知バグ

スキルツリー帯OCRがこのキャラだけ 1/1/1/1/1 になる。ツリー画面の
スクショを撮って skillStrip ROI とラベル位置を確認するところから。
