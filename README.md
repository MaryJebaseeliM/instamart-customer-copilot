**Instamart Customer Intelligence & Support Copilot**
**Overview**
This project combines Python, SQL, Machine Learning and Generative AI to analyse customer behaviour and support operations for an Instamart-style business.
It covers data preparation, customer segmentation, lapse prediction, support-ticket classification, policy retrieval and an AI-based refund agent. The project uses synthetic data and an offline mock LLM.
Reproduce
python -m venv .venv
pip install -r requirements.txt
python generate_data.py
Run the Part A–D Python scripts in the sequence described in their source files. Generated datasets and results are saved in the data/, outputs/ and state/ folders.
**Part A — Data Preparation and SQL Analysis**
Generated synthetic data containing 1,200 customers, 40 products, 13,084 raw orders and 164 support tickets.
Cleaned the customer, product and order datasets and stored them in SQLite (data/instamart.db). The cleaned order dataset contains 12,309 orders: 11,110 completed and 1,199 cancelled. Completed-order revenue is INR 2,998,668.80.
Implemented 7 SQL queries and saved their results as CSV files. Pandas was used to cross-check SQL results and perform exploratory analysis.
Key findings:
•	Mean completed order amount: INR 269.91; median: INR 135.00.
•	Order amount skewness: approximately 4.61.
•	897 order-amount outliers were identified above the upper fence of INR 645.30.
•	The correlation between order amount and discount percentage was approximately -0.095.
**Part B — Customer Segmentation and Lapse Prediction**
Used RFM analysis and K-Means clustering to segment 1,175 customers. The selected model used K=4, with segment sizes of 436, 138, 419 and 182 customers. The silhouette score was 0.526. The first two PCA components explained 63.4% and 21.8% of the variance, respectively (85.2% combined).
The Premium segment contained 138 customers and had the highest mean monetary value: INR 7,129.70.
For lapse prediction, the cohort contained 1,156 customers, including 443 lapsed customers (38.32%). The training and test split contained 924 and 232 customers.
Compared on the same test set:
•	Logistic Regression: F1-score 0.6480.
•	Random Forest: F1-score 0.6591.
Random Forest was selected. Its precision was 0.6667 and recall was 0.6517. Its confusion matrix was [[114, 29], [31, 58]]. The selected model was saved and reloaded with 0 differing test predictions.
A top-10 Premium retention list was generated. It is illustrative: 40 Premium customers were present in the test set, and 2 of the selected 10 were actually lapsed. The Premium flag uses full-window RFM data, so this list is not a leakage-free evaluation.
**Part C — AI Support Ticket Classification**
Processed 164 support tickets using zero-shot and few-shot classification for Billing, Delivery, Technical and Fraud categories. PII redaction, retry handling, token-budget checks and priority-based routing were implemented.
Both approaches classified 147 tickets:
•	Zero-shot accuracy: 85.7%; tokens used: 15,796.
•	Few-shot accuracy: 100%; tokens used: 29,680.
The zero-shot budget demonstration used a 6,000-token budget: 57 tickets were classified, 6,067 actual tokens were used, and 96 tickets were marked budget-exhausted. The final few-shot run used a 100,000-token budget, classified 147 tickets and had 0 budget-exhausted tickets. The remaining 17 tickets were sent for human review.
Fraud tickets are routed to the security team, Premium customers to the premium support desk, and other valid tickets to the general support queue. Invalid, skipped, long or budget-exhausted tickets require human review.
**Part D — Policy Retrieval and Refund Agent**
Loaded 5 policy documents and created 15 chunks using 40-word chunks with 10-word overlap. TF-IDF and cosine similarity retrieve the top 3 relevant chunks.
In the zero-overlap evaluation, the expected document appeared in the top 3 for 12/12 answerable questions, the expected fact was present in 10/12 answers, and the correct fallback was returned for 2/2 unanswerable questions. The results demonstrate that retrieving the correct document does not always guarantee retrieval of the exact supporting fact.
Built a ReAct refund agent with tools for order lookup, policy search, refund calculation, simulated refund issuance and human escalation.
**Refund rules:**
•	Only completed orders are eligible.
•	Delivery later than 45 minutes qualifies for a full refund; 45 minutes or less qualifies for no refund.
•	Refunds above INR 1,000 require human approval.
The agent includes iteration, token and timeout limits, human handoff and checkpoint-based crash recovery. In the resume demonstration, the simulated crash occurred after tool 2; the agent resumed without repeating completed tools and returned a simulated refund of INR 128.25.
**Limitations and Next Steps**
•	The project uses synthetic data and an offline mock LLM, not live customer records or a production LLM.
•	Refund and escalation actions are simulated; no real transactions are performed.
•	Model results are based on the generated dataset and may not generalise to real customer behaviour.
•	The Premium retention list is illustrative and has a full-window RFM limitation.
•	Future improvements could include real-world data validation, production model monitoring, stronger retrieval evaluation and integration with a secure LLM and support platform.
