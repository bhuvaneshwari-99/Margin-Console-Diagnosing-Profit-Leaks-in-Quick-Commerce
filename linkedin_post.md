**I found a ₹4.22M profit leak in 947,752 quick-commerce orders, then built the tool a manager would use to fix it.**

**The finding.** 9.77% of orders lose money. The cause is arithmetic, not mystery: delivery cost rises with distance
(₹29 + ₹8/km in this dataset), so a basket has to clear a break-even that runs from ~₹45 at 2 km to ~₹149 at 15 km.

**What I got wrong first, and fixed.** My first pass said "100% of losses trace to low-value orders." That label was
true by construction, and I'd dismissed distance too fast. Re-checking, I found that cost is a formula of distance,
that "59% more profitable with discounts" is mostly a basket-size effect, and that "attrition" was really loss-order rate.

**The tool.** A Streamlit app: set a minimum order value or small-order fee, then see expected profit, loss-making
orders and lost orders by city and platform, plus the break-even point (how many small-basket customers can leave
before the policy stops paying).

**The honesty part.** The data can't say how customers react, so that's a slider, not a fact. I designed the A/B
test (unit, metric, guardrails, sample size, duration) that would measure it. No fake results.

Stack: Python · SQL (PostgreSQL + BigQuery) · Streamlit · pytest (incl. a SQL-vs-Python cross-check)

Live app: <link> · Code: <link>

#DataAnalytics #SQL #Python #BigQuery #Streamlit #ABTesting
