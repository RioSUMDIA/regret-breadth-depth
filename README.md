# Regret Signals Whether to Search More Broadly or More Deeply

## Associated Manuscript

The materials in this repository were developed for the following manuscript:

**Regret Signals Whether to Search More Broadly or More Deeply**

Authors: Rio Sumida, Hidezo Suganuma, Ryutaro Mori, Yukiko Muramoto, and Tatsuya Kameda

Status: Submitted for peer review on October 9, 2026.

These materials are provided to support the transparency and reproducibility of the research described in the manuscript. The manuscript is currently under review and has not yet been published.

If you use or build upon these materials, please acknowledge the original authors and cite the associated manuscript when it becomes available.

Until the manuscript is published, these materials may be used only for the purpose of evaluating and reproducing the analyses reported in the manuscript; please do not use the data or code in other publications without contacting the authors.

## Contents

| File | Description | Reproduces |
|---|---|---|
| `final_code_v2.qmd` | R (Quarto) code for all statistical analyses of the laboratory experiment | All statistics in the Results, Methods, and SI Appendix; Figures 4 and 5; Figures S1 and S2 |
| `behavior-18.csv` | Trial-level behavioral data from the laboratory experiment | Input to `final_code_v2.qmd` |
| `demographics_2.csv` | Participant sex and age | Input to `final_code_v2.qmd` |
| `data_codebook.csv` | Description of the data columns and how they are used in `final_code_v2.qmd` | — |
| `beta_paper_RS_fixed.ipynb` | Python code for the computational model and simulation | Figure 2 and the benchmark search-set size k* = 16 |
| `data/raw/behavior_data.json` | Raw jsPsych output from the experiment | — |
| `scripts/convert_json_to_csv.py` | Converts the raw JSON into a trial-level CSV (`data/processed/behavior.csv`) | — |
| `data/processed/behavior.csv` | Output of the conversion script (same format as `behavior-18.csv`, plus a `final_choice` column) | — |
| `public/` | Experimental task (HTML/CSS and instruction slides, in Japanese) | — |

The analyses in the paper start from `behavior-18.csv` and `demographics_2.csv`. The raw data, conversion script, and task files are provided for transparency.

## Data

Each row of `behavior-18.csv` is one trial of one participant (13 trials per participant: 3 practice trials followed by 10 main trials). Key columns:

| Column | Meaning |
|---|---|
| `user_id` | Participant identifier |
| `round` | Trial index (0–2: practice; 3–12: main trials 1–10) |
| `explore_count` | Search-set size *k* |
| `explore_count_next`, `explore_count_diff` | Search-set size on the next trial and the trial-to-trial change Δ*k* |
| `outer-regret` | Breadth regret (0–100) |
| `inner-regret` | Depth regret (0–100) |
| `disappointment`, `satisficing`, `successful` | Disappointment, satisfaction, and perceived decision success (0–100) |
| `user_chosen_point` | True value of the chosen option (payoff) |
| `observed_best` | True value of the best option in the search set |
| `global_best` | True value of the best option among all 40 options |

Breadth-deficit loss is `global_best − observed_best`, and depth-deficit loss is `observed_best − user_chosen_point`. See `data_codebook.csv` for the remaining columns.

Exclusions applied in `final_code_v2.qmd`:

- One test record (age ≥ 100 in `demographics_2.csv`) is excluded.
- The three practice trials are excluded.
- Trials affected by a data-storage error (`explore_count == 0`) are excluded, and Δ*k* is set to missing for transitions into such trials.

This yields 64 participants, 631 trials, and 565 trial-to-trial transitions.

## Reproducing the results

### Statistical analyses (R)

Render `final_code_v2.qmd` with Quarto, or run its chunks in order in RStudio, with the repository root as the working directory.

Tested with R 4.5.2 and tidyverse 2.0.0, lme4 2.0.1, lmerTest 3.1.3, nlme 3.1.168, car 3.1.5, patchwork 1.3.2, ggeffects 2.3.1, and pacman 0.5.1. The participant-level bootstrap for the empirical optimum (2,000 resamples, seed 1) takes a few minutes.

### Simulation (Python)

Run all cells of `beta_paper_RS_fixed.ipynb` from top to bottom. The simulation cell generates a `.pkl` data file, which the next cell reads to draw Figure 2 (saved to `img/`).

Settings: 40 options with true values drawn from Beta(2, 2), a sampling budget of T = 40, observation noise σ = 0.5, UGapEb exploration parameter b = 0.001, and 10,000 simulated pools (random seed 777). The full simulation takes about 5 minutes on a recent laptop.

Tested with Python 3.13.3 and numpy 2.5.3, pandas 3.0.6, scipy 1.18.1, matplotlib 3.11.2, and tqdm 4.70.1.
