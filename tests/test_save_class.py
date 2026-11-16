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


def do_block(page):
    """探索(40回観察) → 選択 → 確認 → フィードバック → 後悔アンケート"""
    page.wait_for_selector("#grid .opt")
    # 最初のコックを40回調べる (クリック残数を使い切る)
    page.evaluate("""() => {
      const c = document.querySelector('#grid .opt');
      for (let i = 0; i < 40; i++) c.click();
    }""")
    page.click("#proceed-to-choice")
    page.wait_for_selector("#grid .opt:not(.disabled)")
    page.locator("#grid .opt:not(.disabled)").first.click()
    page.wait_for_selector("#confirm-root")
    click_btn(page, "次へ")
    page.wait_for_selector(".summary-wrap")
    click_btn(page, "次へ")
    # SurveyJS のスライダー (必須) に値を入れて送信
    page.wait_for_selector(".sd-question")
    fill_survey_sliders(page)
    page.locator("input.sd-navigation__complete-btn, .sd-navigation__complete-btn").first.click()


def fill_survey_sliders(page):
    sliders = page.locator("input[type=range]")
    for i in range(sliders.count()):
        sliders.nth(i).focus()
        page.keyboard.press("PageUp")


def run_experiment(page, cond, fail=False):
    if fail:
        page.add_init_script("window.__failSave = true;")
    page.goto(f"file://{PAGE}?cond={cond}")
    # 説明スライド
    page.wait_for_selector(".slide-img")
    for _ in range(SLIDES[cond]):
        page.keyboard.press("ArrowRight")
    click_btn(page, "OK")
    for _ in range(2):  # 練習
        click_btn(page, "開始")
        do_block(page)
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
        do_block(page)
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
