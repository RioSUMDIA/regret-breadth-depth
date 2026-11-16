"""index_conditions_forclass.html の保存テスト (headless / Firebase はモック)。

Firebase SDK を page.route でスタブに差し替え、実UIを高速に操作して最後まで
進め、push() に渡されたペイロードを検証する。本番 DB (post_class) には書き込まない。
"""
import json
import pathlib

import pytest

PAGE = pathlib.Path(__file__).resolve().parents[1] / "public" / "index_conditions_forclass.html"
SLIDES = {"self": 30, "self_best": 35, "full": 39}

APP_STUB = "export const initializeApp = () => ({});"
DB_STUB = """
export const getDatabase = () => ({});
export const ref = (db, path) => ({ path });
export const push = async (r, value) => {
  window.__saved = window.__saved || [];
  window.__saved.push({ path: r.path, value });
  if (window.__pushDelay) await new Promise((res) => setTimeout(res, window.__pushDelay));
  if (window.__failSave) throw new Error("mock save failure");
  return {};
};
"""


@pytest.fixture
def pg(browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.route("**/firebase-app.js", lambda r: r.fulfill(body=APP_STUB, content_type="text/javascript"))
    page.route("**/firebase-database.js", lambda r: r.fulfill(body=DB_STUB, content_type="text/javascript"))
    page.on("pageerror", lambda e: print("PAGEERROR:", e))
    yield page
    ctx.close()


def click_btn(page, text=None):
    loc = page.locator(".jspsych-btn")
    if text:
        loc = loc.filter(has_text=text)
    loc.first.click()


def do_block(page, k=None, ratings=None):
    """探索(40日) → 選択 → 確認 → フィードバック → 後悔アンケート

    k: 探索個数。最初のコックを調べ、「新たなコックを調べる」で k-1 人追加し、
       残りの日数は最初のコックの再観測で消化する(合計40クリック)。None なら 1 人だけ。
    ratings: 5項目の評定値(スライダーの並び順)。None なら PageUp(=10)。
    戻り値: {"k": ..., "ratings": {項目名: 値}}
    """
    page.wait_for_selector("#grid .opt")
    page.wait_for_selector(".choose-msg", state="detached")
    k_used = k or 1
    page.evaluate(
        """(k) => {
      const c = document.querySelector('#grid .opt');
      const add = document.getElementById('add-card');
      c.click();
      for (let i = 0; i < k - 1; i++) add.click();
      for (let i = 0; i < 40 - k; i++) c.click();
    }""",
        k_used,
    )
    page.click("#proceed-to-choice")
    page.wait_for_selector(".choose-msg")
    page.locator("#grid .opt:not(.disabled)").first.click()
    page.wait_for_selector("#confirm-root")
    click_btn(page, "次へ")
    page.wait_for_selector(".summary-wrap")
    click_btn(page, "次へ")
    page.wait_for_selector("input[type=range]")
    set_ratings = fill_survey_sliders(page, ratings)
    page.locator(".sd-navigation__complete-btn").first.click()
    return {"k": k_used, "ratings": set_ratings}


def fill_survey_sliders(page, ratings=None):
    """各スライダーに実キー入力で値を入れ、{項目名: 値} を返す(DOMから読み戻す)。"""
    sliders = page.locator("input[type=range]")
    out = {}
    for i in range(sliders.count()):
        sl = sliders.nth(i)
        sl.focus()
        if ratings is None:
            page.keyboard.press("PageUp")
        else:
            page.keyboard.press("Home")
            for _ in range(ratings[i]):
                page.keyboard.press("ArrowRight")
        name = sl.evaluate("e => e.closest('[data-name]')?.dataset.name")
        out[name] = int(sl.input_value())
        if ratings is not None:
            assert out[name] == ratings[i], f"slider {i} ({name}): {out[name]} != {ratings[i]}"
    return out


def run_experiment(page, cond, fail=False, delay=0, plan=None):
    """plan: ブロックごとの (k, ratings) のリスト(練習2 + 本番10 = 12個)。None なら既定動作。"""
    if fail:
        page.add_init_script("window.__failSave = true;")
    if delay:
        page.add_init_script(f"window.__pushDelay = {delay};")
    page.__done = []
    page.goto(f"file://{PAGE}?cond={cond}")
    # 説明スライド
    page.wait_for_selector(".slide-img")
    for _ in range(SLIDES[cond]):
        page.keyboard.press("ArrowRight")
    click_btn(page, "OK")
    blk = iter(plan or [(None, None)] * 12)
    for _ in range(2):  # 練習
        click_btn(page, "開始")
        page.__done.append(do_block(page, *next(blk)))
    click_btn(page, "確認テストへ")
    # 確認テスト: 全選択
    page.wait_for_selector("input[type=checkbox]")
    boxes = page.locator("input[type=checkbox]")
    for i in range(boxes.count()):
        boxes.nth(i).check()
    click_btn(page, "回答する")
    click_btn(page, "本番を始める")
    for _ in range(10):  # 本番
        click_btn(page, "開始")
        page.__done.append(do_block(page, *next(blk)))
    # 属性
    page.wait_for_selector("text=性別")
    page.locator("text=男性").first.click()
    page.locator(".sd-navigation__complete-btn").first.click()
    click_btn(page, "次へ")  # 最終報酬
    page.wait_for_function("window.__saved && window.__saved.length > 0", timeout=20000)
    return page.evaluate("window.__saved")


@pytest.mark.parametrize("cond", ["self", "self_best", "full"])
def test_result_is_saved(pg, cond):
    saved = run_experiment(pg, cond)
    assert len(saved) == 1
    assert saved[0]["path"] == "post_class"
    rows = json.loads(saved[0]["value"])
    assert {r["feedback_condition"] for r in rows if "feedback_condition" in r} == {cond}
    # 各ブロック(練習2 + 本番10)の結果行: is_practice が入っている行
    blocks = [r for r in rows if r.get("is_practice") is not None]
    assert len(blocks) == 12
    assert sum(r["is_practice"] is False for r in blocks) == 10
    assert all(r["user_chosen_point"] > 0 for r in blocks)
    # 後悔アンケート: 12ブロックぶん、5項目すべて回答あり
    regret = [r["response"] for r in rows if isinstance(r.get("response"), dict) and "outer-regret" in r["response"]]
    assert len(regret) == 12
    for resp in regret:
        for k in ["outer-regret", "inner-regret", "disappointment", "satisficing", "successful"]:
            assert isinstance(resp[k], (int, float)), k
    # 探索回数 (全ブロックで40回観察)
    assert sum(r.get("explore_count") == 40 for r in rows) == 12
    # 最終報酬画面の情報
    assert any(r.get("phase_str") == "FinalReduction" for r in rows)
    pg.wait_for_selector("text=保存完了")


def test_failure_is_reported(pg):
    run_experiment(pg, "full", fail=True)
    pg.wait_for_selector("text=保存に失敗しました")


def test_saved_message_shown_with_slow_network(pg):
    """保存に時間がかかっても、終了画面は保存完了を待ってから「保存完了」を表示する。"""
    run_experiment(pg, "self", delay=400)
    pg.wait_for_selector("text=保存完了", timeout=5000)
    assert "データ保存中" not in pg.inner_text("body")


KS = [3, 5, 28]
RATING_SETS = [[20, 81, 20, 81, 20], [81, 20, 81, 20, 81]]


def test_explore_count_and_ratings_are_saved(pg):
    """探索個数(3, 5, 28)と感情評定(20, 81)をブロックごとに変えて、そのまま保存されるか。"""
    plan = [(KS[i % 3], RATING_SETS[i % 2]) for i in range(12)]
    saved = run_experiment(pg, "full", delay=200, plan=plan)
    rows = json.loads(saved[0]["value"])

    # 探索集合サイズ k: 探索行(observed_choice_order あり)の distinct なコック数
    explore = [r for r in rows if r.get("observed_choice_order")]
    assert len(explore) == 12
    got_k = [len(set(r["observed_choice_order"].split("_"))) for r in explore]
    assert got_k == [KS[i % 3] for i in range(12)]
    assert all(r["explore_count"] == 40 for r in explore)  # 使った日数は常に40

    # 感情評定: 画面で入力した値(DOM読み戻し)が保存値と一致
    resp = [r["response"] for r in rows if isinstance(r.get("response"), dict) and "outer-regret" in r["response"]]
    assert len(resp) == 12
    for i, (r, done) in enumerate(zip(resp, pg.__done)):
        for name, v in done["ratings"].items():
            assert r[name] == v, f"block {i}: {name} saved {r[name]} != entered {v}"
        assert sorted(r[n] for n in done["ratings"]) == sorted(RATING_SETS[i % 2])
