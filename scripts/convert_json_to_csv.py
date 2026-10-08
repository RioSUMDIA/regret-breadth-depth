# /// script
# requires-python = ">=3.10"
# dependencies = ["polars", "numpy"]
# ///
"""data/raw/behavior_data.json (jsPsych の生データ) を試行単位の CSV に変換する。

出力: data/processed/behavior.csv (behavior-18.csv と同じ形式)
実行: uv run scripts/convert_json_to_csv.py
"""

from pathlib import Path
import json
import numpy as np
import polars as pl
import polars.selectors as cs

PJ_DIR = Path(__file__).parents[1]
DATA_DIR = PJ_DIR / "data"
RAW_JSON_PATH = DATA_DIR / "raw" / "behavior_data.json"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_CSV_PATH = PROCESSED_DIR / "behavior.csv"


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_raw_dict(raw_json_data: dict):
    def _convert_object_to_dict(dict_value: str):
        return json.loads(dict_value)

    res_dict = {}
    for key, val in raw_json_data.items():
        converted_val = _convert_object_to_dict(val)
        res_dict[key] = converted_val
    return res_dict


def add_reaction_time_col(raw_df: pl.DataFrame) -> pl.DataFrame:
    return (
        raw_df.with_columns(
            pl.col("time_elapsed").shift(1).alias("time_elapsed_m1"),
        )
        .with_columns(
            (pl.col("time_elapsed") - pl.col("time_elapsed_m1")).alias("rt"),
        )
        .drop("time_elapsed", "time_elapsed_m1")
    )


def extract_survey_data(raw_df: pl.DataFrame):
    df = raw_df.filter(pl.col("trial_type") == "survey")
    df = df.unnest("response")
    df = df.rename({"rt": "survey_rt"})
    return df.select(
        "survey_rt",
        "inner-regret",
        "outer-regret",
        "satisficing",
        "disappointment",
        "successful",
    ).with_row_index()


# ジニ係数を計算する関数
def calculate_gini(x):
    if x is None or len(x) == 0:
        return None
    # 昇順にソート
    x = np.array(sorted(x), dtype=float)
    n = len(x)
    if n == 0 or np.sum(x) == 0:
        return 0.0
    # インデックスを用いた計算式
    index = np.arange(1, n + 1)
    return (np.sum((2 * index - n - 1) * x)) / (n * np.sum(x))


def add_choice_gini_coefficient(raw_df: pl.DataFrame):
    df = (
        raw_df.with_columns(
            pl.col("observed_choice_order").str.split("_").alias("choice_list"),
        )
        .filter(pl.col("choice_list").list.len() > 1)
        .with_columns(pl.col("choice_list").cast(pl.List(pl.Int64)))
    )
    df = df.with_columns(
        gini_index=pl.col("choice_list").map_elements(
            calculate_gini, return_dtype=pl.Float64
        )
    )
    return df.with_row_index()


def extract_explore_data(raw_df: pl.DataFrame):
    df = add_reaction_time_col(raw_df)
    df = df.rename({"rt": "explore_rt"})

    df = df.filter(pl.col("observed_choice_order") != "")

    df = df.with_columns(
        pl.col("observed_choice_order")
        .str.split("_")
        .cast(pl.List(pl.Int16))
        .alias("choice_list"),
    ).with_columns(pl.col("choice_list").list.max().alias("explore_count"))

    return df.select("explore_rt", "explore_count").with_row_index()


def extract_choice_results_data(raw_df: pl.DataFrame):
    df = add_reaction_time_col(raw_df)
    df = df.drop_nulls(pl.col("user_observed_max_point"))
    df = df.rename(
        {
            "user_chosen_point": "user_chosen_point",
            "user_unchosen_max_point": "global_best",
            "user_observed_max_point": "observed_best",
            "finalChoice": "final_choice",
        }
    )
    return df.select(
        "user_chosen_point", "global_best", "observed_best", "final_choice"
    ).with_row_index()


def add_explore_diff(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("explore_count")
        .shift(-1)
        .over(pl.col("user_id"))
        .alias("explore_count_next")
    ).with_columns(
        (pl.col("explore_count_next") - pl.col("explore_count")).alias(
            "explore_count_diff"
        )
    )


def remove_unused_cols(raw_df):
    if "added_idx" in raw_df.columns:
        raw_df = raw_df.drop("added_idx")
    if "after_first_observed" in raw_df.columns:
        raw_df = raw_df.drop("after_first_observed")
    df = raw_df.drop(cs.struct(), cs.list())
    return df


def process_behavior_data(raw_json_data: dict):
    cleaned_dict = clean_raw_dict(raw_json_data)

    is_first_df = True
    for user_id, val in cleaned_dict.items():
        raw_df = pl.DataFrame(val)

        survey_df = extract_survey_data(raw_df)
        explore_df = extract_explore_data(raw_df)
        choice_result_df = extract_choice_results_data(raw_df)
        gini_df = add_choice_gini_coefficient(raw_df)

        user_ids = pl.Series("user_id", [user_id] * choice_result_df.height)
        joined_df = (
            survey_df.join(explore_df, on="index")
            .join(choice_result_df, on="index")
            .join(gini_df, on="index")
            .rename({"index": "round"})
            .with_columns(user_ids)
        )

        joined_df = remove_unused_cols(joined_df)

        if is_first_df:
            res_df = joined_df
            is_first_df = False
        else:
            res_df = pl.concat([res_df, joined_df])

    res_df = add_explore_diff(res_df)
    return res_df


if __name__ == "__main__":
    json_data = read_json(RAW_JSON_PATH)

    behavior_df = process_behavior_data(json_data)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    behavior_df.write_csv(OUTPUT_CSV_PATH)
    print(
        f"Wrote {behavior_df.height} rows "
        f"({behavior_df['user_id'].n_unique()} participants) to {OUTPUT_CSV_PATH}"
    )
