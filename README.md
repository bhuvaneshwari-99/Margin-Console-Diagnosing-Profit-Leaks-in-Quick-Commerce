# Margin Console: find the profit leak, then test the fix

**Python · SQL (PostgreSQL + BigQuery) · Streamlit · A/B-test design**


> 9.77% of 947,752 quick-commerce orders lose money. This project shows *why*, turns that into a what-if tool a manager can use to set a minimum order value or small-order fee, and designs the A/B test that would replace the tool's assumptions with measured customer behaviour.

<!-- Add a screenshot or GIF of the app here: docs/app_demo.gif -->

---

## TL;DR

| | |
|---|---|
| **Question** | Where do orders lose money, and what would a minimum order value or small-order fee do to profit? |
| **Data** | 947,752 quick-commerce orders (Kaggle, 13 columns), cleaned and enriched |
| **Answer** | Losses are arithmetic: delivery cost rises with distance, and small baskets don't clear it |
| **Deliverables** | (1) Analysis notebook and SQL, (2) Streamlit what-if app, (3) A/B test design |
| **Not claimed** | Customer response. The data has no sessions or carts, so that is a slider, not a fact |

---

## Key results

| Metric | Value |
|---|---|
| Loss-making orders | **92,592 (9.77%)** |
| Aggregate deficit | **₹4.22M** |
| Average loss per loss-making order | **₹45.61** |
| Delivery cost formula (fitted, correlation with distance = 1.0) | **₹29 + ₹8 × km** |
| Break-even basket | **~₹45 at 2 km → ~₹149 at 15 km** (before discounts) |

### What drives the losses
A loss happens when the basket is smaller than the trip costs to deliver. **Distance sets the bar; basket size decides whether it is cleared.** A flat minimum order value is therefore too blunt, and a **distance-tiered small-basket fee** targets the mechanism directly.

### Other findings

| Finding | Numbers | Read it as |
|---|---|---|
| **Discounted orders are larger and more profitable** | Basket ₹712 vs ₹476; profit ₹614 vs ₹385 (+59%); Welch t = 284.8 | **Association, not causation.** The ₹228.6 profit gap = ₹235.8 basket gap − ₹7.1 average discount. Delivery cost is identical across groups, so the discount is a cost, not a driver. Discounted baskets are ~49% larger in every age group. Whether discounts *cause* bigger baskets needs an experiment. |
| **Faster deliveries are more profitable** | 0-15 min: ₹527 profit, 6.88% loss-order rate, ₹76 delivery cost. 31-45 min: ₹282, 23.07%, ₹115 | Mostly near vs far (cost depends on distance). The notebook holds distance fixed. |
| **Platforms** | Jio Mart: lowest avg margin (58.3%), highest loss-order rate (10.81%), smallest basket (₹483). Swiggy Instamart: 64.9%, 9.21%, ₹645 | Differences are driven by basket size. |
| **Cities** | Haridwar (₹342 avg profit/order) and Jaipur trail Gurgaon (₹600) on every platform | Gap is market-level (basket and distance mix), not platform-specific. |

> With n ≈ 948k, p < 0.001 is guaranteed, so the notebook reports effect sizes and intervals, and compares like-for-like within basket bands rather than relying on p-values.

### Corrections made along the way
An earlier version of this analysis said *"100% of losses are Low Value Orders; distance is not a cause."* That was wrong:
- The "Low Value Order" label is true **by construction** (it tests order value < ₹300 first), so it proves nothing.
- Distance **is** the cause of the break-even moving, since cost is an exact function of distance.
- "Attrition" was really **loss-order rate**, which is not customer churn.

The corrected analysis is in the notebook's summary table.

---

## The what-if app

Set a minimum order value or small-order fee in the sidebar:

| Output | What it answers |
|---|---|
| Profit change, loss-making %, orders lost | What does this policy do overall? |
| Change decomposition | Is the gain from top-ups, fees, or shedding loss-makers? |
| City / platform table + heatmap | Where does it help or hurt? |
| Threshold sweep + sensitivity grid | Is my threshold robust to customer behaviour? |
| Break-even | How many small-basket customers can leave before the policy stops paying? |
| Experiment design | How many carts and how many days to test it properly? |

**Adjustable assumptions:** top-up rate, abandon rate, delivery-cost stress test, contribution-margin slider (100% reproduces the dataset).

---

## Read before quoting any number

- **Cost is modelled, not observed.** The source has no cost fields. `Delivery_Cost`, `Discount_Amt`, `Profit`, `In_Loss` and `Loss_Driver` were derived. A delivery-cost stress-test slider exists for this reason.
- **Profit is before product cost** (order value − delivery − discount). Real contribution margins are much lower, which would make far more orders loss-making. Use the contribution-margin slider.
- **The dataset looks simulated.** Platforms, cities and categories are each almost perfectly evenly split. Rankings demonstrate method, not facts about real companies.
- **Customer response is assumed.** No sessions, carts or timestamps exist, so top-up and abandon rates are sliders, not estimates.
- **"Loss rate" is the share of orders with negative profit.** It is not customer attrition.

---

## The experiment (design only, no results)

- **Unit and arms:** randomise customers between "no minimum" and "minimum ₹X" (optionally a fee arm).
- **Primary metric:** contribution profit per eligible cart, with abandoned carts counted as ₹0 so lost orders are priced in.
- **Guardrails:** cart→order conversion, 28-day repeat orders, ratings.
- **Sample size and duration:** calculated in the app's *Experiment design* tab from the data's own variance plus stated assumptions.
- **Closing the loop:** the measured result feeds straight back into the tool's top-up and abandon sliders.

---

## Method and testing

- **Cleaning and validation:** `scripts/prepare_data.py` validates the CSV and writes parquet/CSV.
- **Analysis:** SQL in PostgreSQL and BigQuery (same logic, two dialects), plus the notebook for EDA and statistics.
- **Engine:** expected-profit model, break-even maths and cost fit in `margin_console/model.py`.
- **Tests (pytest):** engine, app UI, SQL, and a **SQL-vs-Python cross-check** so both implementations agree.

---

## Repository

```
streamlit_app.py             the what-if app
margin_console/
  model.py                   expected-profit engine, break-even maths, cost fit
  ab_design.py               sample size and duration
  data.py                    BigQuery -> local parquet -> synthetic fallback
  demo_data.py               synthetic stand-in (tests + fallback only)
notebooks/q_comm.ipynb       cleaning, EDA, statistics, export
sql/quick_comm_postgres.sql  PostgreSQL analysis (executed in tests)
sql/quick_comm_bigquery.sql  BigQuery version
scripts/prepare_data.py      validate + clean CSV -> parquet/CSV
scripts/load_to_bigquery.py  load into BigQuery
tests/                       engine, app UI, SQL (incl. SQL-vs-Python cross-check)
docs/linkedin_post.md        write-up
```

## Run it

```bash
pip install -r requirements-dev.txt
python scripts/prepare_data.py path/to/quick_comm2.csv   # validates, writes data/orders*.parquet
streamlit run streamlit_app.py
python -m pytest -q                                       # engine, UI, SQL cross-check
```

Without any data file the app opens on clearly labelled synthetic data.

<details>
<summary><b>Put the data in BigQuery</b></summary>

```bash
gcloud auth application-default login
python scripts/load_to_bigquery.py --project YOUR_PROJECT --dataset margin_console
```

Then run `sql/quick_comm_bigquery.sql`. The table is roughly 100 MB, well inside the free tier. BigQuery sandbox tables expire after 60 days by default; enable billing on the project (free tier still applies) if you want it to persist.
</details>

<details>
<summary><b>Deploy free on Streamlit Community Cloud</b></summary>

1. Push the repo to GitHub (do **not** commit `.streamlit/secrets.toml`; it is git-ignored).
2. In BigQuery/IAM create a service account with *BigQuery Job User* (project) and *BigQuery Data Viewer* (dataset).
3. share.streamlit.io → New app → `streamlit_app.py`. Under Settings → Secrets paste the contents of `.streamlit/secrets.toml.example` filled in with your key.
4. The sidebar footer shows which source is live (BigQuery, Local parquet or Synthetic demo). If BigQuery fails, the app says so and falls back rather than hiding it.

Check the Kaggle dataset licence before committing `data/orders.parquet`; if unsure, keep the data in BigQuery only.
</details>

---

## Possible next steps
- Run the A/B test on real traffic and feed results into the sliders.
- Replace the fitted delivery-cost formula with observed cost data.
- Add product-level contribution margin instead of the single slider.

## Contact
**Bhuvaneshwari L** · lbhuvaneshwari729@gmail.com · [LinkedIn](#) · [GitHub](#)
