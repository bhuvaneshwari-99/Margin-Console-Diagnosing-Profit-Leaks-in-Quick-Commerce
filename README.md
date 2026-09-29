

Readme · MD
# Margin Console: find the profit leak, then test the fix
 
**[▶ Live app](https://YOUR-APP-NAME.streamlit.app)** · Python · SQL (PostgreSQL + BigQuery) · Streamlit · A/B-test design
 
Quick-commerce platforms run on thin margins, and small baskets are expensive to deliver. This project
(1) quantifies where 947,752 orders lose money, (2) turns that into a **what-if tool** where a manager sets a minimum
order value or small-order fee and sees the expected change in profit, loss-making orders and lost orders by city and
platform, and (3) designs the **A/B test** that would replace the tool's assumptions with measured behaviour.
 
## Try it
 
Set a threshold in the sidebar and the app shows:
 
| Output | What it answers |
|---|---|
| Profit change, loss-making %, orders lost | What does this policy do overall? |
| Change decomposition | Is the gain from top-ups, fees, or shedding loss-makers? |
| City / platform table + heatmap | Where does it help or hurt? |
| Threshold sweep + sensitivity grid | Is my threshold robust to customer behaviour? |
| Break-even | How many small-basket customers can leave before the policy stops paying? |
| Experiment design | How many carts and how many days to test it properly? |
 
## Findings
 
The numbers below come from `notebooks/q_comm.ipynb` on the full 947,752-order table.
 
1. **9.77% of orders are loss-making**: 92,592 orders, ₹4.22M aggregate deficit, ₹45.61 average loss per loss-making order.
2. **A loss happens when the basket is smaller than the trip costs to deliver.** In this table `Delivery_Cost` is
   exactly ₹29 + ₹8 × km (correlation with distance = 1.0), so the break-even basket rises from about ₹45 at 2 km to
   about ₹149 at 15 km (before discounts). Distance sets the bar; basket size decides whether it is cleared.
   *(An earlier version said "100% of losses are Low Value Orders, distance is not a cause". That label is true by
   construction, since it tests order value < 300 first, and the distance claim was wrong. See the notebook summary table.)*
3. **Discounted orders are larger and more profitable on average**: basket ₹712 vs ₹476, profit ₹614 vs ₹385 (+59%),
   Welch t = 284.8. That is an association, and the arithmetic shows why: the ₹228.6 profit gap is the ₹235.8 basket
   gap minus the ₹7.1 average discount, so delivery cost is identical across the two groups and the discount is a cost,
   not a driver. Discounted baskets are ~49% larger in every age group. The notebook compares like-for-like within
   basket bands and reports effect size and interval, since p < 0.001 is guaranteed at n ≈ 948k. Whether discounts
   *cause* larger baskets needs an experiment.
4. **Faster deliveries are more profitable**: 0-15 min orders average ₹527 profit vs ₹282 for 31-45 min (1.9×), with a
   6.88% vs 23.07% loss-order rate (3.4× lower) and ₹76 vs ₹115 delivery cost. Cost depends on distance, so
   this mostly reflects near vs far; the notebook holds distance fixed.
5. **Platforms**: Jio Mart has the lowest average margin (58.3%) and highest loss-order rate (10.81%) vs Swiggy Instamart
   (64.9%, 9.21%). Jio Mart also has the smallest average basket (₹483 vs ₹645).
6. **Cities**: Haridwar (₹342 avg profit/order) and Jaipur trail Gurgaon (₹600) on every platform, so the gap is
   market-level (basket and distance mix), not platform-specific.
**Bottom line:** a minimum order value or a distance-tiered small-basket fee targets the mechanism directly. How
much it earns depends on how customers respond, which this data cannot say. Hence the tool and the test.
 
## Read before quoting any number
 
* **Cost is modelled, not observed.** The Kaggle source has 13 columns and no cost fields. `Delivery_Cost`,
  `Discount_Amt`, `Profit`, `In_Loss` and `Loss_Driver` were derived. The app has a delivery-cost stress-test slider for this reason.
* **`Profit` is before product cost** (order value − delivery − discount). Real contribution margins are much
  lower, which would make far more orders loss-making. The app has a contribution-margin slider; at 100% it reproduces the dataset.
* **The dataset looks simulated** (platforms, cities and categories are each almost perfectly evenly split).
  Platform and city rankings demonstrate method, not facts about real companies.
* **Customer response is assumed.** There are no sessions, carts or timestamps, so top-up and abandon rates
  are sliders, not estimates.
* "Loss rate" is the share of orders with negative profit. It is **not** customer attrition.
## Repository
 
```
streamlit_app.py            the what-if app
margin_console/
  model.py                  expected-profit engine, break-even maths, cost fit
  ab_design.py              sample size and duration
  data.py                   BigQuery → local parquet → synthetic fallback
  demo_data.py              synthetic stand-in (tests + fallback only)
notebooks/q_comm.ipynb      cleaning, EDA, statistics, export
sql/quick_comm_postgres.sql PostgreSQL analysis (executed in tests)
sql/quick_comm_bigquery.sql BigQuery version
scripts/prepare_data.py     validate + clean CSV → parquet/CSV
scripts/load_to_bigquery.py load into BigQuery
tests/                      engine, app UI, SQL (incl. SQL-vs-Python cross-check)
docs/linkedin_post.md       write-up
```
 
## Run it
 
```bash
pip install -r requirements-dev.txt
python scripts/prepare_data.py path/to/quick_comm2.csv     # validates, writes data/orders*.parquet
streamlit run streamlit_app.py
python -m pytest -q                                         # engine, UI, SQL cross-check
```
 
Without any data file the app opens on clearly labelled synthetic data.
 
### Put the data in BigQuery
```bash
gcloud auth application-default login
python scripts/load_to_bigquery.py --project YOUR_PROJECT --dataset margin_console
```
Then run `sql/quick_comm_bigquery.sql`. The table is roughly 100 MB, well inside the free tier. BigQuery *sandbox*
tables expire after 60 days by default; enable billing on the project (free tier still applies) if you want it to persist.
 
### Deploy free on Streamlit Community Cloud
1. Push the repo to GitHub (do **not** commit `.streamlit/secrets.toml`; it is git-ignored).
2. In BigQuery/IAM create a service account with *BigQuery Job User* (project) and *BigQuery Data Viewer* (dataset).
3. share.streamlit.io → New app → `streamlit_app.py`. Under **Settings → Secrets** paste the contents of
   `.streamlit/secrets.toml.example` filled in with your key.
4. The sidebar footer shows which source is live (`BigQuery`, `Local parquet` or `Synthetic demo`).
   If BigQuery fails, the app says so and falls back rather than hiding it.
Check the Kaggle dataset licence before committing `data/orders.parquet`; if unsure, keep the data in BigQuery only.
 
## The experiment (design only, no results)
 
Randomise customers between "no minimum" and "minimum ₹X" (optionally a fee arm). Primary metric: **contribution profit
per eligible cart**, with abandoned carts counted as ₹0 so lost orders are priced in. Guardrails: cart→order
conversion, 28-day repeat orders, ratings. Sample size and duration are calculated in the app's *Experiment design* tab
from the data's own variance plus stated assumptions. The result feeds straight back into the tool's top-up/abandon
sliders.
 
## Contact
 
Bhuvaneshwari L · lbhuvaneshwari729@gmail.com · [LinkedIn](https://www.linkedin.com/in/bhuvaneshwaril/) · [GitHub](https://github.com/bhuvaneshwari-99)
