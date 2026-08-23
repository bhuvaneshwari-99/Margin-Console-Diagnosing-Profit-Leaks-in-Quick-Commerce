# Margin Console: Diagnosing Profit Leaks in Quick-Commerce
Data Analytics Project analyzing order-level profitability for quick-commerce platforms using SQL, Excel,Python (EDA,Statistical) and Power BI.
-

# 📊 Data Analytics Project

## 🧭 Overview

This project replicates a **real-world quick-commerce profitability analysis**, similar to work done by data analysts at companies like **Swiggy Instamart, Blinkit, Zepto, and BigBasket**.

It involves cleaning and exploring a **large-scale transactional dataset (1M+ records)**, running **SQL queries (PostgreSQL)** to uncover loss-making patterns, performing supporting analysis in **Excel**, and building an **interactive Power BI dashboard** to visualize profitability, delivery performance, and discount impact.

The goal is to identify which orders, products, and locations are losing money — and provide data-backed recommendations to improve margins.

---

## 📂 Dataset

* **Source:** [Quick Commerce Dataset – Kaggle](https://www.kaggle.com/datasets/rohitgrewal/quick-commerce-dataset)
* **Format:** CSV
* **Size:** ~1,000,000 records
* **Description:** Order-level data including customer, location, product category, basket value, delivery cost, discounts, delivery time, and customer rating.
* **Target Outcome:** Identify profitability drivers, loss-making segments, and actionable cost-optimization insights.

---

## ⚙️ Tools & Technologies
| Category                        | Tools Used                                 |
| ------------------------------- | ------------------------------------------ |
| Database                        | PostgreSQL                                 |
| SQL IDE                         | pgAdmin / DBeaver                          |
| Programming Language            | Python                                     |
| Python Environment              | Jupyter NoteBook                           |
| Data Analysis                   | Pandas, NumPy,Matplotlib,Seaborn           |
| Statistics                      | Descriptive Statistics, Hypothesis Testing |
| Experimentation                 | A/B Testing                                |
| Exploratory Data Analysis (EDA) | Pandas, Matplotlib, Seaborn                |
| Data Cleaning                   | Excel, Power Query, Python                 |
| Data Visualization              | Power BI, Matplotlib, Seaborn              |
| Business Intelligence           | Power BI                                   |
| Spreadsheet Analysis            | Microsoft Excel                            |

---

## 🔑 Key Insights

Here are the key insights from your analysis:

**1. The benchmark**
9.77% of all orders are loss-making — every other finding is measured against this baseline, not in isolation.

**2. The one true root cause**
100% of loss-making orders trace back to "Low Value Order" — 92,592 orders, ₹4.22M aggregate deficit, ₹45.61 average loss per order. Distance and discounting correlate with lower profit, but they don't independently *cause* losses the way basket size does.

**3. Discounting helps, it doesn't hurt**
Discounted orders are 59% more profitable on average (₹614 vs ₹385 profit), confirmed with Welch's t-test (p < 0.001, n = 947,752). The uplift is consistent across every age group (~49–50%), so age-based targeting won't move the needle — category or distance-based targeting would be smarter.

**4. Speed = profit**
Orders delivered in 0–15 minutes are ~1.9x more profitable than the 31–45 minute tier, and have 3x lower attrition (6.88% vs 23.07%). Slower deliveries also cost more to fulfill (₹115 vs ₹76), compounding the loss.

**5. Platform gap**
Jio Mart has the thinnest margin (58.3%) and highest attrition (10.81%) of all 8 platforms — a 6.6-point gap behind the leader, Swiggy Instamart (64.9% margin, 9.21% attrition).

**6. It's geography, not platform execution**
Haridwar and Jaipur underperform across *every single platform* — a ₹258 gap between the best city (Gurgaon, ₹600 avg profit/order) and worst (Haridwar, ₹342). Since the pattern holds market-wide, it points to local cost structure or demand density, not platform-specific mismanagement.

**7. Order value is king**
Pearson correlation between order value and profit is a near-perfect 1.00 — basket size is by far the biggest lever, dwarfing distance (r = −0.09).

**Bottom line:** one fix — a minimum order value or distance-tiered delivery fee — addresses almost the entire tracked loss. Everything else (speed, city, platform, discounting) is a secondary lever.
---
🔍 How I traced ₹4.22M in losses back to a single root cause — a quick-commerce profitability deep dive

**Situation**
Quick-commerce platforms compete on 10-minute delivery, but run on razor-thin margins. Revenue, delivery cost, discounts, and customer data were scattered across disconnected reports — nobody could say with confidence *where* orders were actually losing money.

**Task**
I set out to analyze 947,752 transactions across 8 platforms and 12 cities, and pinpoint exactly where and why profit was leaking — then turn that into concrete, actionable recommendations.

**Action**
I ran the analysis end-to-end across three tools, each suited to its stage:
→ SQL / PostgreSQL — schema design and first-pass exploration (revenue, AOV, top cities/categories, payment mix)
→ Python / Pandas — data validation, feature engineering, segment comparisons, and formal hypothesis testing (Welch's t-test, Pearson correlation)
→ Power BI — an interactive "Margin Console" dashboard to filter and explore results by platform, city, category, distance, and rating

**Result**
The findings were sharper than expected:
• 9.77% of orders were loss-making — the benchmark every other cut was measured against
• 100% of loss-making orders traced back to one cause: low order value (₹4.22M aggregate deficit, 92,592 orders)
• Discounted orders were 59% MORE profitable on average (₹614 vs ₹385), confirmed at p < 0.001 — discounting isn't the villain
• Fastest deliveries (0-15 min) were ~1.9x more profitable and had 3x lower attrition than the slowest tier
• Jio Mart trailed the pack by 6.6 points of margin vs. Swiggy Instamart; Haridwar and Jaipur underperformed across every single platform — a market-level, not platform-level, issue

The single highest-leverage fix: a minimum order value or distance-tiered delivery fee — one lever that addresses nearly the entire tracked loss.

Sometimes the biggest business insight isn't a new discount strategy — it's the discipline to trace every rupee back to its source.

#DataAnalytics #SQL #Python #PowerBI #QuickCommerce #BusinessIntelligence #DataStorytelling
---
## 📬 Contact

Bhuvaneshwari L
📧 Email: lbhuvaneshwari729@gmail.com

🌐 LinkedIn: https://www.linkedin.com/in/bhuvaneshwaril/

💻 GitHub: https://github.com/bhuvaneshwari-99
