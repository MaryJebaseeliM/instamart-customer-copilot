# Instamart Customer Intelligence & Support Copilot

## Overview

This project implements a reproducible customer intelligence and support workflow using synthetic Instamart-style data. It covers raw data auditing, data cleaning, SQLite storage, customer segmentation, lapse prediction, support ticket triage, policy retrieval, and a simulated refund agent.

All data is synthetic. LLM interactions use the supplied offline `mock_llm.py`; no external LLM API is required.


Part A — Data Quality, Cleaning and Database Setup
*************************************************
1. Objective

The objective of Part A was to inspect the raw Instamart datasets, identify data-quality issues, apply consistent cleaning rules, and prepare reliable data for SQL analysis and subsequent customer intelligence tasks.

The raw datasets were generated using generate_data.py and stored in data/raw/. The cleaned datasets were saved in data/clean/, and the validated data was loaded into the SQLite database data/instamart.db.

Task 1## Reproduce
******************************************
1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Generate the synthetic source data:

   ```powershell
   python generate_data.py
   ```

   Expected final line:

   `generated: customers=1200 products=40 orders_raw=13084 tickets=164`

4. Run the Part A audit and cleaning scripts:

   ```powershell
   python audit_data.py
   python clean_customers.py
   python clean_orders.py
   ```

Task 2. Raw Data Audit
******************************************
I used audit_data.py to examine the raw customer, product and order data before applying any cleaning rules. The audit checked for duplicate records, missing values, invalid numeric values, inconsistent category names and unexpected values.

The audit identified the following issues:

Data-quality check	Raw data finding
Raw order rows	13,084
Exact duplicate order rows	119
Duplicate order IDs with different records	Investigated during order cleaning
Pending order rows	656
Distinct order IDs	12,309
Non-numeric order amounts	120
Negative delivery times	106
Blank delivery times	2,541
Customers with missing ages	61
Customer ages outside the valid range of 10–100	6
Distinct raw city spellings	24
Distinct non-blank gender spellings	10
Customers with blank gender values	30

The audit results were saved to outputs/raw_audit_results.csv. These findings were used to define the cleaning rules rather than modifying the raw files directly.

Task 3. Customer Data Cleaning
*********************************************
The script clean_customers.py was used to standardise customer records and handle missing or invalid values.

The following rules were applied:

City standardisation: Leading and trailing spaces were removed, and city names were standardised using title case. The cleaned data contains six standard city names: Bengaluru, Chennai, Delhi, Hyderabad, Mumbai and Pune.
Gender standardisation: Gender values were mapped to male, female or unknown. Blank or unrecognised values were assigned unknown.
Age validation: Ages outside the valid range of 10–100 were treated as missing.
Missing-age imputation: Missing and invalid ages were filled using the median age of the corresponding city.
Date handling: signup_date was converted to a consistent datetime format.

The cleaned customer data was saved to data/clean/customers.csv.

Validation confirmed 1,200 customer records, six standardised cities, 610 female records, 560 male records and 30 records with unknown gender. No missing ages remained after cleaning, and the cleaned age range was 18–60.

Product Data Cleaning

The script clean_products.py was used to prepare the product dataset for analysis.

The raw product data was read from data/raw/products.csv and saved to data/clean/products.csv. The product identifiers, names, categories and prices were retained so that orders could be joined to the product catalogue during SQL analysis.

The product dataset contains 40 products. No additional transformations were applied where the existing values already satisfied the project requirements.

Task 4. Order Data Cleaning
*******************************************
The script clean_orders.py was used to clean the order records and ensure that order amounts and delivery times were suitable for analysis.

The following cleaning rules were applied:

Timestamp standardisation: order_ts was converted to datetime format.
Exact duplicate removal: Exact duplicate order rows were removed.
Duplicate order IDs: Where the same order_id appeared in different records, the record with the latest order_ts was retained.
Order amount conversion: order_amount was converted to a numeric value. Invalid or non-numeric amounts were treated as missing.

Order amount imputation: Missing order amounts were calculated using the product price, quantity and discount percentage:

order_amount = round(price_inr × quantity × (1 − discount_pct / 100), 2)

Delivery-time validation: Negative delivery times were treated as missing values.
Missing delivery-time imputation: For completed orders with missing delivery times, the missing value was filled using the median delivery time for the corresponding product category among completed orders.
Cancelled orders: Missing delivery times were retained for cancelled orders because a delivery time may not be applicable to an order that was not completed.
Pending orders: Pending orders were excluded from the final cleaned order dataset according to the project's cleaning rules.

The cleaned order dataset was saved to data/clean/orders.csv.

After cleaning, the dataset contained 12,309 orders: 11,110 completed and 1,199 cancelled. There were no pending orders or missing order amounts. Completed orders had no missing delivery times, while the 1,199 cancelled orders retained missing delivery times. Total completed-order revenue was INR 2,998,668.80.

Task 5:Store and validate
***********************************************
The script store_validate.py loaded the cleaned customer, product and order datasets into the SQLite database data/instamart.db.

The database contains the following three tables:

Table	Description
customers	Cleaned customer details, including city, gender, age and signup date
products	Product identifiers, names, categories and prices
orders	Cleaned order records, including customer and product identifiers, order status, order amount and delivery time

The database allows the datasets to be joined using their identifiers. For example, the orders table can be joined to customers using customer_id and to products using product_id.

Task 6 sql analysis
************************************************
All seven SQL queries are saved in sql/queries.sql and executed against data/instamart.db using pandas.read_sql_query() in run_sql_analysis.py. Completed orders are used for revenue and customer spend unless the query explicitly examines all order statuses.

After loading the data, store_validate.py checked the cleaned datasets against the expected project checkpoints. The checks covered record counts, distinct identifiers, customer city and gender values, age validity, order-status counts, missing values, completed-order revenue and timestamp formatting.

The validation script is expected to print:

ALL CHECKPOINTS PASSED


The runner executes all seven SQL statements with pd.read_sql_query(), prints result previews, saves each result as a CSV, and checks the reference counts and totals.


TaskAfter running the SQL analysis,The SQL runner creates the outputs/sql/ folder and saves seven CSV result files there.
sql/queries.sql — contains Q1 through Q7.

outputs/sql/ — contains the seven query result CSVs.

data/instamart.db — the SQLite database queried by the script

 Task 7:pandas-cross check and exploratory analysis
*************************************************
Pivot-table cross-check: I rebuilt the SQL city/category revenue analysis using pd.pivot_table() with margins=True. The All grand-total cell should equal the SQL revenue total of INR 2,998,668.80.

City-level statistics: Using groupby() and named aggregation on completed orders, Bengaluru has a total of INR 523,643.40, a mean order amount of INR 276.47 and 1,894 orders. Mumbai has a total of INR 479,058.50, a mean of INR 297.00 and 1,613 orders.

Distribution and outlier analysis: The analysis calculates the mean, median, skewness, Q1, Q2, Q3, IQR, 1.5×IQR fences and counts of outliers below and above the fences.

Exploratory interpretation

What is this data about? It describes Instamart orders, including order amounts, discounts, quantities, delivery times, cities and product categories.

What do its distributions and statistics look like? Completed order amounts have a mean of INR 269.91, median of INR 135.00 and skewness of approximately 4.61. The distribution is strongly right-skewed; Q1 is INR 64.80 and Q3 is INR 297.00.

Are there outliers or anomalies? The lower fence is INR -283.50 and the upper fence is INR 645.30. There are no outliers below the lower fence and 897 above the upper fence. These unusually large orders warrant investigation but are not automatically errors.

What relationships exist between variables? order_amount and discount_pct have the largest absolute correlation, approximately -0.095; order_amount and quantity correlate at approximately +0.087. These relationships are weak, and correlation of this size does not establish causation.

Part A Deliverables
*******************************

The main outputs produced in Part A are:

outputs/raw_audit_results.csv — raw data-quality audit results.
data/clean/customers.csv — cleaned customer dataset.
data/clean/products.csv — prepared product dataset.
data/clean/orders.csv — cleaned order dataset.
data/instamart.db — SQLite database containing the three cleaned tables.

Part A establishes a consistent and validated data foundation for the SQL analysis in the following section.

**************************************

## Part B — Customer Segmentation and Lapse Prediction
************************************************
#### Objective

bjective

The objective of Part B is to identify meaningful customer segments from Instamart's completed order history and build a machine learning model that predicts which customers are likely to stop ordering. The analysis uses RFM (Recency, Frequency and Monetary value), K-means clustering and PCA to profile customers, then compares tuned Logistic Regression and Random Forest classifiers to predict customer lapse. The selected model is evaluated on an untouched test set, saved and reloaded to verify reproducibility, and used to create an illustrative retention list for high-value Premium customers who may need targeted retention campaigns.

All customer behaviour features for lapse prediction are calculated using orders before 1 September 2025 to prevent future order information from leaking into model training. Preprocessing is fitted on training data only, and model performance is evaluated using precision, recall, F1-score and confusion matrices. A class-balancing experiment also examines how oversampling affects the detection of lapsing customers.

### Task 1. Build the RFM Table (build_rfm.py)
****************************************
The objective of this task was to summarise customer purchasing behaviour using RFM analysis. The RFM table provides a customer-level view of how recently and frequently customers ordered and how much they spent. These features can be used for customer segmentation and retention campaign planning.

#### Input Data

The analysis uses the cleaned datasets produced in Part A:

* `data/clean/orders.csv`
* `data/clean/customers.csv`

Only orders with status `completed` were included when calculating customer behaviour. Cancelled and other non-completed orders were excluded.

#### RFM Definitions

The snapshot moment was set to **2025-10-01 00:00:00**.

For each customer with at least one completed order, the following metrics were calculated:

| Metric    | Definition                                                                                      | Interpretation                                          |
| --------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Recency   | Whole number of days between the snapshot moment and the customer's most recent completed order | Lower values indicate more recent purchasing activity   |
| Frequency | Number of distinct completed orders placed by the customer                                      | Higher values indicate more frequent purchasing         |
| Monetary  | Sum of `order_amount` across the customer's completed orders                                    | Higher values indicate greater completed-order spending |

Recency was calculated using the difference between the snapshot timestamp and the customer's latest completed-order timestamp, followed by `.dt.days`. Frequency was calculated by counting distinct completed `order_id` values, while monetary value was calculated by summing completed `order_amount` values.

#### Implementation

The completed order timestamps were converted to datetime format before calculating recency. The orders were then grouped by `customer_id` to calculate the three RFM metrics. The resulting table contains one row per customer with at least one completed order.

The RFM table was saved as `outputs/rfm_table.csv`.

#### Validation Results

The expected reference results are:

| Check                                       | Reference result |
| ------------------------------------------- | ---------------: |
| Customers with at least one completed order |            1,175 |
| Median recency                              |          19 days |
| Minimum recency                             |           0 days |
| Maximum recency                             |         180 days |
| Mean frequency                              |      9.46 orders |
| Maximum frequency                           |        33 orders |
| Mean monetary value                         |     INR 2,552.06 |
| Maximum monetary value                      |    INR 14,766.55 |

These statistics are used to validate the RFM table. The results should be reported as confirmed only after running the implementation and comparing the actual output with these reference values.

#### Outcome

The RFM table provides a structured summary of customer activity and spending. Recency helps identify customers who have not ordered recently, frequency distinguishes occasional customers from frequent customers, and monetary value highlights customers who contribute more completed-order revenue. These features form the foundation for the customer segmentation and lapse prediction tasks that follow.

### Task 2. K-means Customer Clustering(cluster_customer.py)
**************************************************88
#### Objective

The objective was to group customers with similar purchasing behaviour into meaningful segments using their Recency, Frequency and Monetary (RFM) metrics. These segments can help the retention team design targeted campaigns for customers with different levels of engagement and spending.

#### Data Preparation

The RFM table generated in Task 1 was used as input. The three numerical features—`recency`, `frequency` and `monetary`—were standardised using `StandardScaler` so that differences in their numerical scales would not disproportionately influence the clustering process.

K-means was fitted for each value of K from 2 to 8 using `n_init=10` and `random_state=42`. For each model, inertia and the silhouette score were recorded to assess cluster compactness and separation.

#### Evaluation Results

The reference results are shown below. These values must be checked against the results produced by the project code before final submission.

|  K | Inertia | Silhouette score |
| -: | ------: | ---------------: |
|  2 |  1820.8 |            0.465 |
|  3 |  1268.2 |            0.445 |
|  4 |   743.1 |            0.526 |
|  5 |   617.4 |            0.481 |
|  6 |   503.2 |            0.482 |
|  7 |   408.5 |            0.416 |
|  8 |   366.5 |            0.412 |

#### Elbow Analysis and Final K

The inertia decreases as K increases, but the reduction is particularly substantial between K=3 and K=4. After K=4, the reductions become smaller relative to the additional number of clusters, suggesting diminishing returns from adding more segments.

**The selected value is K=4.** It has the highest silhouette score in the reference results (0.526), indicating better cluster separation than the other tested values. Four segments also offer a practical balance between meaningful differences in customer behaviour and the number of campaigns the retention team can manage.

#### Why the Lowest Inertia Does Not Automatically Mean the Best K

Inertia measures how close customers are to their assigned cluster centres. Increasing K gives the algorithm more centres, so inertia generally decreases as clusters become smaller; therefore, K=8 is expected to have lower inertia than K=2. However, choosing K solely by minimum inertia would favour adding more clusters, even when the extra groups are not meaningfully different or useful for business decisions.

#### Business Interpretation

The four clusters were examined using their RFM characteristics to understand differences in customer activity and spending. Cluster labels are numerical identifiers, not business descriptions; the segments should be named only after reviewing each cluster's RFM profile. The resulting customer-segment file is intended to support retention campaign planning and provide customer-segment information to Part C's ticket-routing workflow.


### RFM segmentation

- Snapshot: 2025-10-01 00:00:00.
- Use completed orders to calculate recency, frequency, and monetary value.
- Standardise RFM features and evaluate KMeans for K = 2 through 8, using `n_init=10` and `random_state=42`.
- Report inertia and silhouette score for each K, justify the selected K, describe each segment, and report PCA explained variance.
- Define premium customers as the segment with the highest mean monetary value.

Expected reference values: 1,175 customers; median recency 19 minutes, minimum 0 and maximum 180; mean frequency 9.46 and maximum 33; mean monetary value INR 2,552.06 and maximum INR 14,766.55.

Reference KMeans results:

| K | Inertia | Silhouette |
|---:|---:|---:|
| 2 | 1820.8 | 0.465 |
| 3 | 1268.2 | 0.445 |
| 4 | 743.1 | 0.526 |
| 5 | 617.4 | 0.481 |
| 6 | 503.2 | 0.482 |
| 7 | 408.5 | 0.416 |
| 8 | 366.5 | 0.412 |

Reference K=4 segment sizes are approximately 436, 138, 419, and 182. PCA variance ratios are approximately 0.634 and 0.218, totalling 0.852.

### Task 3. Profile, Name and Project the Segments
************************************************
#### Segment Profiles and Business Actions

The four K-means segments were profiled using the mean recency, mean frequency and mean monetary value of their customers. Business names were assigned after examining these RFM characteristics.

* **Occasional, Lower-Spend Customers:** Encourage additional purchases through relevant product bundles and targeted promotions.
* **Premium — High-Value Customers:** Provide personalised offers and loyalty rewards. This segment has the highest mean monetary value and is therefore marked as Premium.
* **Frequent, Recently Active Customers:** Encourage repeat purchases through loyalty incentives and subscription offers.
* **Lapsed or At-Risk Customers:** Use win-back campaigns and targeted offers to encourage customers to order again.

Cluster IDs are arbitrary labels generated by the clustering algorithm; their numerical order does not indicate customer value or importance. The Premium designation is determined by comparing mean monetary value across the segments.

#### Principal Component Analysis

PCA was applied to the standardised RFM matrix using `PCA(n_components=2)`. The explained variance ratios for the first and second principal components were recorded, along with their combined explained variance. The two components provide a lower-dimensional representation of the RFM features while retaining a substantial portion of their variation.

#### Output Files

* `outputs/customer_segments.csv` contains the customer ID, RFM metrics, segment ID, segment name and Premium flag.
* `outputs/cluster_profiles.csv` contains the segment sizes and mean RFM metrics.
* `outputs/kmeans_metrics.csv` contains inertia and silhouette scores for K values from 2 to 8.
 final output of task3
 
 K-means evaluation:
 K  inertia  silhouette
 2 1820.761       0.465
 3 1268.235       0.445
 4  743.071       0.526
 5  617.367       0.480
 6  503.171       0.482
 7  408.460       0.416
 8  366.503       0.412

Segment profiles (MEANS):
 segment_id                        segment_name  is_premium  customer_count  mean_recency  mean_frequency  mean_monetary
          0   Occasional, Lower-Spend Customers       False             436         28.86            3.77        1057.62
          1      Premium - High-Value Customers        True             138         24.12            6.77        7129.70
          2 Frequent, Recently Active Customers       False             419          8.77           19.40        3410.02
          3         Lapsed or At-Risk Customers       False             182        109.04            2.20         685.99

PCA explained variance ratio:
PC1: 0.634
PC2: 0.218
Total: 0.852

Premium segment ID: 1
Premium mean monetary value: 7129.7
Saved outputs/customer_segments.csv
Saved outputs/cluster_profiles.csv
Saved outputs/kmeans_metrics.csv

Task 3. Profile, Name and Project the Segments
***************************************************
Segment Profiles and Business Actions

The four K-means segments were profiled using the mean recency, mean frequency and mean monetary value of their customers. Business names were assigned after examining these RFM characteristics.

Occasional, Lower-Spend Customers: Encourage additional purchases through relevant product bundles and targeted promotions.
Premium — High-Value Customers: Provide personalised offers and loyalty rewards. This segment has the highest mean monetary value and is therefore marked as Premium.
Frequent, Recently Active Customers: Encourage repeat purchases through loyalty incentives and subscription offers.
Lapsed or At-Risk Customers: Use win-back campaigns and targeted offers to encourage customers to order again.

Cluster IDs are arbitrary labels generated by the clustering algorithm; their numerical order does not indicate customer value or importance. The Premium designation is determined by comparing mean monetary value across the segments.

Task 4.define lapse problem :(build_lapse_dataset.py)
************************************************
4. Define the Lapse Prediction Problem
Cohort and Target Label

The lapse prediction task uses a cutoff date of 1 September 2025. The cohort includes customers with at least one completed order strictly before the cutoff, resulting in a reference cohort of 1,156 customers.

The target label is determined from completed orders during September 2025. A customer is labelled lapsed = 1 if they have no completed order from 1 September through 30 September, and lapsed = 0 otherwise. The reference cohort contains 443 lapsed customers, corresponding to a lapse rate of 38.32%.

Feature Engineering and Leakage Prevention

All behavioural features are calculated using orders dated strictly before the cutoff. These features include recency, frequency, monetary value, average discount percentage, cancellation rate, average delivery time and most frequent product category. Customer city, age, gender and tenure in days are taken from the clean customer data.

Cancellation rate is calculated as cancelled orders divided by all orders with a final status before the cutoff. Pending orders are excluded from this denominator. The target label uses September activity, but September orders are never included in the model features. Customer segment IDs and segment names from Task 3 are also excluded to prevent target leakage.

Train/Test Split and Baseline

The dataset is split using train_test_split(test_size=0.2, stratify=y, random_state=42). The reference split contains 924 training rows and 232 test rows.

As a baseline, a classifier that always predicts not lapsed achieves approximately 61.6% accuracy but an F1 score of 0 for the lapsed class. This illustrates why accuracy alone is insufficient for an imbalanced classification problem: the baseline fails to identify any lapsed customers.

The modelling dataset is saved to outputs/lapse_dataset.csv. All feature engineering is based on information available before the cutoff, while September completed-order activity is used only to define the target label.

Task 5:Preprocess without leakage
***************************************
Script:build_lapse_dataset.py.
. Preprocessing Without Data Leakage

The lapse prediction features were preprocessed using a scikit-learn ColumnTransformer containing separate numerical and categorical pipelines.

Numerical features were standardised using StandardScaler. The nominal features city, gender and most_frequent_category were one-hot encoded using OneHotEncoder(drop="first"), producing reference-category encoding with one fewer column per categorical variable.

The dataset was split using train_test_split(test_size=0.2, stratify=y, random_state=42) before fitting the preprocessing pipeline. The pipeline was fitted using only the training features. The fitted transformations were then applied to the test features without refitting the scaler or encoder. This prevents test-set information from influencing preprocessing.

The code checks for missing values in every input feature and in both transformed matrices. The fitted preprocessing pipeline was saved to outputs/lapse_preprocessor.joblib, and the transformed training and test datasets were saved separately.

The frequency mean learned by the scaler can differ from the full-cohort frequency mean because the scaler is fitted only on the training subset, while the full-cohort mean includes both training and test customers.

Task 6 Train, tune and evaluate:
*****************************************
Script:train_lapse_models.py

Task 6: Train, Tune and Evaluate

(a) Baseline

The baseline predicts every customer as not lapsed. The test-set accuracy was [insert accuracy], while the F1-score for the lapsed class was 0.00. Although this baseline can achieve reasonable accuracy because non-lapsed customers form the majority class, it fails to identify lapsing customers.

(b) Logistic Regression

LogisticRegression(max_iter=1000) was tuned using GridSearchCV over C = [0.01, 0.1, 1, 10, 100], with 5-fold cross-validation and scoring="f1".

Best parameters: [insert best parameters]
Best cross-validated F1: [insert CV F1]
Test confusion matrix: [insert matrix]
Test precision for the lapsed class: [insert precision]
Test recall for the lapsed class: [insert recall]
Test F1 for the lapsed class: [insert F1]

(c) Random Forest

RandomForestClassifier(n_estimators=100, random_state=42) was tuned over max_depth = [3, 5, 8] and min_samples_leaf = [5, 10, 20], using 5-fold cross-validation and scoring="f1". The search evaluated 9 parameter combinations, resulting in 45 fits.

Best parameters: [insert best parameters]
Best cross-validated F1: [insert CV F1]
Test confusion matrix: [insert matrix]
Test precision for the lapsed class: [insert precision]
Test recall for the lapsed class: [insert recall]
Test F1 for the lapsed class: [insert F1]

(d) Model selection

I selected [insert selected model] because its test F1 for the lapsed class was [insert F1]. Missing a customer who is about to lapse may mean losing future orders and revenue, so false negatives are costly. However, wrongly targeting loyal customers also has a cost because retention discounts and campaign effort may be wasted. I therefore considered the lapsed-class precision and recall alongside F1, and selected the model that best balances identifying at-risk customers with avoiding unnecessary targeting. The selected model [met/did not meet] the assignment's minimum test F1 requirement of 0.55.

a) Baseline

The baseline predicts every customer as not lapsed. Its test accuracy was 0.6164, but its precision, recall, and F1-score for the lapsed class were all 0.0000. Although it correctly classified the 143 non-lapsed customers, it failed to identify any of the 89 lapsed customers.

(b) Logistic Regression

LogisticRegression(max_iter=1000) was tuned using GridSearchCV with C = [0.01, 0.1, 1, 10, 100], 5-fold cross-validation, and scoring="f1".

Best parameters: C = 100
Best cross-validated F1: 0.6506
Test confusion matrix: [[111, 32], [31, 58]]
Lapsed-class precision: 0.6444
Lapsed-class recall: 0.6517
Lapsed-class F1: 0.6480
Test accuracy: 0.7284
(c) Random Forest

RandomForestClassifier(n_estimators=100, random_state=42) was tuned over max_depth = [3, 5, 8] and min_samples_leaf = [5, 10, 20], using 5-fold cross-validation and scoring="f1". The grid search evaluated 9 parameter combinations and performed 45 fits.

Best parameters: max_depth = 8, min_samples_leaf = 10
Best cross-validated F1: 0.6829
Test confusion matrix: [[114, 29], [31, 58]]
Lapsed-class precision: 0.6667
Lapsed-class recall: 0.6517
Lapsed-class F1: 0.6591
Test accuracy: 0.7414
(d) Selected model and justification

I selected the Random Forest because it achieved the higher test F1-score of 0.6591, exceeding the required minimum of 0.55. Missing a customer who is about to lapse can result in lost future orders and revenue, so false negatives are costly. However, wrongly targeting loyal customers also wastes retention discounts and campaign resources. The Random Forest achieved the same recall as Logistic Regression while improving precision from 0.6444 to 0.6667 and reducing false positives from 32 to 29. Therefore, it provides the better balance of identifying lapsing customers and avoiding unnecessary retention offers among these two tested models.

Saved outputs:

outputs/lapse_model_test_results.csv
outputs/lapse_model_tuning_results.json

Task 7:class-balance experiment:
*******************************************
Script: experiment_class_balance.py

The lapsed class was the minority in the training data, with 570 non-lapsed customers and 354 lapsed customers. I retained all original training rows and randomly oversampled lapsed rows with replacement using random_state=42, adding 216 duplicate rows to obtain balanced training counts of 570 per class.

I refitted the best Logistic Regression configuration from Task 6 (C=100, max_iter=1000) on both the original and balanced training sets. Both models were evaluated on the same unchanged test set of 232 customers.

Metric for lapsed class	Original training data	Balanced training data
Precision	0.6444	0.5891
Recall	0.6517	0.8539
F1-score	0.6480	0.6972
Test accuracy	0.7284	0.7155

The largest absolute change was in recall, which increased by 0.2022, from 0.6517 to 0.8539. The balanced model identified 76 of the 89 lapsed customers, compared with 58 using the original training data, and reduced false negatives from 31 to 13. However, precision fell from 0.6444 to 0.5891, and false positives increased from 32 to 53. For the retention team, this means fewer at-risk customers are missed, but more loyal customers receive potentially unnecessary retention offers, so the additional campaign cost should be weighed against the benefit of retaining more customers.

Saved outputs:

outputs/lapse_train_balanced.csv
outputs/lapse_class_balance_results.csv

Task 8:Interpret, persist and use
*************************************
Script: interpret_persist.py

Random Forest feature importance: The five most important features were frequency (0.280860), monetary (0.269613), recency (0.113665), average delivery time (0.061707), and cancellation rate (0.052742). Frequency and monetary value were the two strongest contributors to the model's predictions.

Logistic Regression coefficients: The frequency coefficient was negative (-1.697333), the Electronics category coefficient was negative (-1.135167), and the Grocery category coefficient was negative (-0.449305). Higher frequency was associated with lower predicted lapse odds, holding other features constant. The category coefficients represent associations relative to the omitted reference category, not causal effects.

Model persistence: I saved the selected Random Forest model to outputs/lapse_model.joblib using joblib.dump and reloaded it using joblib.load. The original and reloaded models produced exactly matching test predictions, with 0 differing predictions.

Premium retention list: I filtered the test-set customers to those marked Premium in the Task 3 customer segments, ranked them by predicted lapse probability in descending order, and saved the top 10 to outputs/retention_list.csv. There were 40 Premium customers in the test set, and 2 of the 10 selected customers were actually lapsed.

The retention list is illustrative and not a leakage-free evaluation because the Premium flag is derived from whole-window RFM data that includes the September period used to define the lapse label, although the model's predictive features use only orders before the 1 September 2025 cutoff.

Saved outputs:

outputs/task8_rf_top5_importance.csv
outputs/task8_lr_top3_coefficients.csv
outputs/lapse_model.joblib
outputs/retention_list.csv


Principal Component Analysis

PCA was applied to the standardised RFM matrix using PCA(n_components=2). The explained variance ratios for the first and second principal components were recorded, along with their combined explained variance. The two components provide a lower-dimensional representation of the RFM features while retaining a substantial portion of their variation.

Output Files
outputs/customer_segments.csv contains the customer ID, RFM metrics, segment ID, segment name and Premium flag.
outputs/cluster_profiles.csv contains the segment sizes and mean RFM metrics.
outputs/kmeans_metrics.csv contains inertia and silhouette scores for K values from 2 to 8.


### Lapse prediction

- Cutoff: 2025-09-01.
- Define the cohort and lapse label exactly as specified.
- Prevent temporal leakage by deriving features only from pre-cutoff data.
- Split with `test_size=0.2`, `stratify=y`, and `random_state=42`.
- Compare Logistic Regression and Random Forest with the required cross-validation grids.
- Report baseline, best parameters, cross-validation F1, test confusion matrices, precision, recall, F1, feature importance, and selected-model results.
- Oversample the training set only and evaluate on the unchanged test set.
- Save the selected model and verify predictions after reloading it.
- Create the premium-customer retention list ranked by predicted lapse probability.

Reference cohort: 1,156 customers; 443 lapsed (38.32%); split 924/232. Reference Logistic Regression F1 is approximately 0.62; Random Forest F1 is approximately 0.65. Explain that the retention list is illustrative/post-hoc because the premium segment uses a full-window RFM calculation.

ouput of task 4
Training rows: 924
Test rows: 232
Baseline accuracy: 0.616
Baseline lapsed-class F1: 0.0

Feature columns:
['recency', 'frequency', 'monetary', 'avg_discount_pct', 'cancellation_rate', 'avg_delivery_minutes', 'most_frequent_category', 'city', 'age', 'gender', 'tenure_days']

Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_dataset.csv

5. Preprocessing Without Data Leakage

The lapse prediction features were preprocessed using a scikit-learn ColumnTransformer containing separate numerical and categorical pipelines.

Numerical features were standardised using StandardScaler. The nominal features city, gender and most_frequent_category were one-hot encoded using OneHotEncoder(drop="first"), producing reference-category encoding with one fewer column per categorical variable.

The dataset was split using train_test_split(test_size=0.2, stratify=y, random_state=42) before fitting the preprocessing pipeline. The pipeline was fitted using only the training features. The fitted transformations were then applied to the test features without refitting the scaler or encoder. This prevents test-set information from influencing preprocessing.

The code checks for missing values in every input feature and in both transformed matrices. The fitted preprocessing pipeline was saved to outputs/lapse_preprocessor.joblib, and the transformed training and test datasets were saved separately.

The frequency mean learned by the scaler can differ from the full-cohort frequency mean because the scaler is fitted only on the training subset, while the full-cohort mean includes both training and test customers.

output of task 5
Missing values per feature:
recency                   0
frequency                 0
monetary                  0
avg_discount_pct          0
cancellation_rate         0
avg_delivery_minutes      0
age                       0
tenure_days               0
city                      0
gender                    0
most_frequent_category    0

Missing-value check passed: all feature columns are complete.

Training rows: 924
Test rows: 232
Transformed training matrix has no missing values.
Transformed test matrix has no missing values.

Frequency mean comparison:
Training-only scaler mean: 8.1147
Full-cohort frequency mean: 8.0285

Number of transformed features: 19
Transformed feature names:
['numeric__recency', 'numeric__frequency', 'numeric__monetary', 'numeric__avg_discount_pct', 'numeric__cancellation_rate', 'numeric__avg_delivery_minutes', 'numeric__age', 'numeric__tenure_days', 'categorical__city_Chennai', 'categorical__city_Delhi', 'categorical__city_Hyderabad', 'categorical__city_Mumbai', 'categorical__city_Pune', 'categorical__gender_male', 'categorical__gender_unknown', 'categorical__most_frequent_category_Electronics', 'categorical__most_frequent_category_Grocery', 'categorical__most_frequent_category_Personal Care', 'categorical__most_frequent_category_Snacks']

Saved:
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_train_processed.csv
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_test_processed.csv
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_preprocessor.joblib

output of task6:
======================================================
Confusion matrix [[TN, FP], [FN, TP]]:
[[143   0]
 [ 89   0]]
Accuracy:  0.6164
Precision: 0.0000
Recall:    0.0000
Lapsed F1: 0.0000

======================================================
LOGISTIC REGRESSION GRID SEARCH
======================================================
Best parameters: {'C': 100}
Best mean CV F1: 0.6506

======================================================
RANDOM FOREST GRID SEARCH
======================================================
Parameter combinations: 9
CV fits: 45
Best parameters: {'max_depth': 8, 'min_samples_leaf': 10}
Best mean CV F1: 0.6829

Tuned Logistic Regression
---------------------------------------------
Confusion matrix [[TN, FP], [FN, TP]]:
[[111  32]
 [ 31  58]]
Accuracy:  0.7284
Precision: 0.6444
Recall:    0.6517
Lapsed F1: 0.6480

Tuned Random Forest
---------------------------------------------
Confusion matrix [[TN, FP], [FN, TP]]:
[[114  29]
 [ 31  58]]
Accuracy:  0.7414
Precision: 0.6667
Recall:    0.6517
Lapsed F1: 0.6591

Saved:
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_model_test_results.csv
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_model_tuning_results.json

Selected model by test lapsed F1: Tuned Random Forest
Selected test F1: 0.6591
Selected model meets the minimum test F1 requirement of 0.55

ask 7: Class-Balance Experiment

The lapsed class was oversampled in the training set only. All original training rows were retained, and randomly selected lapsed training rows were duplicated with replacement using random_state=42 until both classes had equal counts.

The best Logistic Regression configuration from Task 6 (C=100, max_iter=1000) was fitted twice: once on the original training data and once on the balanced training data. Both models were evaluated on the same unchanged test set.

Task 7: Class-Balance Experiment

The lapsed class was the minority in the training data, with 570 non-lapsed customers and 354 lapsed customers. I retained all original training rows and randomly oversampled lapsed rows with replacement using random_state=42, adding 216 duplicate rows to obtain balanced training counts of 570 per class.

I refitted the best Logistic Regression configuration from Task 6 (C=100, max_iter=1000) on both the original and balanced training sets. Both models were evaluated on the same unchanged test set of 232 customers.

Metric for lapsed class	Original training data	Balanced training data
Precision	0.6444	0.5891
Recall	0.6517	0.8539
F1-score	0.6480	0.6972
Test accuracy	0.7284	0.7155

The largest absolute change was in recall, which increased by 0.2022, from 0.6517 to 0.8539. The balanced model identified 76 of the 89 lapsed customers, compared with 58 using the original training data, and reduced false negatives from 31 to 13. However, precision fell from 0.6444 to 0.5891, and false positives increased from 32 to 53. For the retention team, this means fewer at-risk customers are missed, but more loyal customers receive potentially unnecessary retention offers, so the additional campaign cost should be weighed against the benefit of retaining more customers.

Saved outputs:

outputs/lapse_train_balanced.csv
outputs/lapse_class_balance_results.csv

output of task 7:
======================================================
ORIGINAL TRAINING CLASS COUNTS
============================================================
0 = not lapsed, 1 = lapsed
lapsed
0    570
1    354
Name: count, dtype: int64

======================================================
BALANCED TRAINING CLASS COUNTS
======================================================
lapsed
0    570
1    570
Name: count, dtype: int64
Duplicate rows added: 216

Logistic Regression - Original Training Data
---------------------------------------------
Confusion matrix [[TN, FP], [FN, TP]]:
[[111  32]
 [ 31  58]]
Accuracy:  0.7284
Precision: 0.6444
Recall:    0.6517
Lapsed F1: 0.6480

Logistic Regression - Oversampled Training Data
---------------------------------------------
Confusion matrix [[TN, FP], [FN, TP]]:
[[90 53]
 [13 76]]
Accuracy:  0.7155
Precision: 0.5891
Recall:    0.8539
Lapsed F1: 0.6972

======================================================
METRIC COMPARISON
======================================================
lapsed_precision: 0.6444 -> 0.5891 (change: -0.0553)
lapsed_recall: 0.6517 -> 0.8539 (change: +0.2022)
lapsed_f1: 0.6480 -> 0.6972 (change: +0.0492)

Largest absolute change: lapsed_recall

Saved:
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_train_balanced.csv
C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_class_balance_results.csv

### Task 8: Interpret, Persist and Use the Model

**Random Forest feature importance:** The five most important features were frequency (0.280860), monetary (0.269613), recency (0.113665), average delivery time (0.061707), and cancellation rate (0.052742). Frequency and monetary value were the two strongest contributors to the model's predictions.

**Logistic Regression coefficients:** The frequency coefficient was negative (-1.697333), the Electronics category coefficient was negative (-1.135167), and the Grocery category coefficient was negative (-0.449305). Higher frequency was associated with lower predicted lapse odds, holding other features constant. The category coefficients represent associations relative to the omitted reference category, not causal effects.

**Model persistence:** I saved the selected Random Forest model to `outputs/lapse_model.joblib` using `joblib.dump` and reloaded it using `joblib.load`. The original and reloaded models produced exactly matching test predictions, with 0 differing predictions.

**Premium retention list:** I filtered the test-set customers to those marked Premium in the Task 3 customer segments, ranked them by predicted lapse probability in descending order, and saved the top 10 to `outputs/retention_list.csv`. There were 40 Premium customers in the test set, and 2 of the 10 selected customers were actually lapsed.

The retention list is illustrative and not a leakage-free evaluation because the Premium flag is derived from whole-window RFM data that includes the September period used to define the lapse label, although the model's predictive features use only orders before the 1 September 2025 cutoff.

**Saved outputs:**

* `outputs/task8_rf_top5_importance.csv`
* `outputs/task8_lr_top3_coefficients.csv`
* `outputs/lapse_model.joblib`
* `outputs/retention_list.csv`

task 8 output
Training rows: 924
Test rows: 232
Transformed features: 19

(a) TOP 5 RANDOM FOREST FEATURES
                      feature  importance
           numeric__frequency    0.280860
            numeric__monetary    0.269613
             numeric__recency    0.113665
numeric__avg_delivery_minutes    0.061707
   numeric__cancellation_rate    0.052742

(a) THREE LOGISTIC REGRESSION COEFFICIENTS
                                        feature  coefficient     sign
                             numeric__frequency    -1.697333 negative
categorical__most_frequent_category_Electronics    -1.135167 negative
    categorical__most_frequent_category_Grocery    -0.449305 negative

(b) MODEL PERSISTENCE CHECK
Saved model: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\lapse_model.joblib
Reloaded predictions exactly match: True
Number of differing predictions: 0

(c) PREMIUM CUSTOMER RETENTION LIST
Premium customers in test set: 40
Rows written to retention list: 10
Truly lapsed customers in retention list: 2
customer_id  lapse_probability  actually_lapsed
      C0862           0.488354                0
      C1112           0.481379                0
      C0060           0.476802                0
      C0802           0.473219                0
      C1008           0.471826                0
      C1000           0.463484                0
      C0188           0.456674                1
      C0525           0.456089                1
      C0267           0.455559                0
      C0167           0.454941                0

Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\retention_list.csv

Task 8 completed.

### Required Part B outputs

- `outputs/customer_segments.csv`
- `outputs/lapse_model.joblib`
- `outputs/retention_list.csv`
********************************************

## Part C — Support Ticket Triage
***********************************************
### Ticket preparation and classification

- Read `tickets.csv` with `keep_default_na=False`.
- Skip empty tickets and flag very long tickets before making model calls.
- Redact email addresses, phone numbers, and order IDs before passing ticket text to the mock LLM.
- Compare zero-shot and few-shot classification using the required four categories: billing, delivery, technical, and fraud.
- Retry transient failures up to 3 times with exponential backoff and jitter.
- Validate JSON output and use the specified keyword fallback when JSON is invalid.

Reference input counts: 164 tickets, 4 empty tickets, 4 long tickets, and 734 estimated tokens per long ticket. Reference redactions: 55 emails, 91 phone numbers, and 132 order IDs, totalling 278.

Reference classification results: 19 transient errors recovered; few-shot processing yields 135 JSON results, 12 keyword-fallback results, and 9 invalid results. Zero-shot accuracy is approximately 85.7%; few-shot accuracy is 100% over classified tickets.

************************

task 1 output

Tickets processed: 164

Status counts:
status
eligible         156
skipped_empty      4
flagged_long       4

Maximum token estimate among flagged-long tickets:
734

Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\task1_guardrail_audit.csv

Task 1 guardrail checks passed.

### Task 2: Redact Personal Information:
*******************************************
Script:redact_tickets.py

I applied the three required regular expressions to ticket text in the specified order: email addresses, phone numbers, and order IDs. Matches were replaced with `[EMAIL]`, `[PHONE]`, and `[ORDER_ID]`, respectively, before ticket text could be included in a model prompt.

**Results across all 164 tickets:**

| Information type | Substitutions |
| ---------------- | ------------: |
| Email addresses  |            55 |
| Phone numbers    |            91 |
| Order IDs        |           132 |
| **Total**        |       **278** |

After redaction, I re-applied all three regular expressions to every redacted ticket and confirmed that zero matches remained. The script includes assertions for the expected substitution counts and the zero-match verification.

The redacted text was saved to `outputs/redacted_tickets.csv`. The original raw ticket file was not modified. For model calls, the message content consists of the redacted ticket text alone, without additional text or ticket metadata.

**Output:** `outputs/redacted_tickets.csv`

Task 3:2 prompts
*******************************************
I created two system prompts to classify customer support tickets into one of four allowed categories: billing, delivery, technical, and fraud.
Zero-shot prompt: Classifies a ticket without providing example tickets. It includes the CLASSIFY instruction and requires a JSON-only response in the format {"category": "...", "reason": "..."}. It does not contain EXAMPLES:.
Few-shot prompt: Uses the same classification rules and JSON response format, with an EXAMPLES: section containing labelled billing, delivery, technical, and fraud examples to guide the model.
Both prompts restrict the category to the four permitted values and require a brief reason in the JSON response, with no additional text or Markdown.
Validation: Both prompts contain CLASSIFY and list all four categories. The zero-shot prompt excludes EXAMPLES:, while the few-shot prompt includes EXAMPLES: followed by at least two labelled examples, including a fraud example.


Task 4: Resilient LLM Calls
****************************************
Script:Resilien_Calls.py

I implemented a retry wrapper in resilient_calls.py to handle TransientLLMError exceptions. Each eligible ticket receives an initial attempt and up to three retries. Retry delays use exponential backoff with jitter, following BASE_DELAY × 2**n × random.uniform(0.9, 1.15), with BASE_DELAY = 0.05 seconds and retry exponents 0, 1 and 2.
Each retry logs the ticket ID, retry number and wait duration. I called mock_llm.reset() immediately before the full batch run.
Results: All 156 eligible tickets completed successfully. The run encountered 19 transient errors, recovered all 19 through retries, and ended with zero permanent errors. All Task 4 assertions passed. Results were saved to outputs/task4_retry_results.csv.

output
Retry: ticket_id=T0002, retry_number=1, wait=0.0452s
Retry: ticket_id=T0116, retry_number=1, wait=0.0473s
Retry: ticket_id=T0153, retry_number=1, wait=0.0476s
Retry: ticket_id=T0039, retry_number=1, wait=0.0494s
Retry: ticket_id=T0152, retry_number=1, wait=0.0510s
Retry: ticket_id=T0043, retry_number=1, wait=0.0456s
Retry: ticket_id=T0111, retry_number=1, wait=0.0453s
Retry: ticket_id=T0155, retry_number=1, wait=0.0531s
Retry: ticket_id=T0100, retry_number=1, wait=0.0467s
Retry: ticket_id=T0068, retry_number=1, wait=0.0569s
Retry: ticket_id=T0135, retry_number=1, wait=0.0566s
Retry: ticket_id=T0009, retry_number=1, wait=0.0572s
Retry: ticket_id=T0067, retry_number=1, wait=0.0499s
Retry: ticket_id=T0106, retry_number=1, wait=0.0548s
Retry: ticket_id=T0097, retry_number=1, wait=0.0540s
Retry: ticket_id=T0003, retry_number=1, wait=0.0567s
Retry: ticket_id=T0019, retry_number=1, wait=0.0572s
Retry: ticket_id=T0086, retry_number=1, wait=0.0532s
Retry: ticket_id=T0065, retry_number=1, wait=0.0562s

--- Task 4 Retry Summary ---
Eligible tickets: 156
Successful tickets: 156
Transient errors: 19
Recovered errors: 19
Permanent errors: 0
Results saved to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\task4_retry_results.csv
ALL TASK 4 CHECKS PASSED

Task 5:validate every answer:
****************************************
Loaded original labels for 164 tickets.
Retry: ticket_id=T0002, retry_number=1, wait=0.0536s
Retry: ticket_id=T0116, retry_number=1, wait=0.0553s
Retry: ticket_id=T0153, retry_number=1, wait=0.0489s
Retry: ticket_id=T0039, retry_number=1, wait=0.0547s
Retry: ticket_id=T0152, retry_number=1, wait=0.0460s
Retry: ticket_id=T0043, retry_number=1, wait=0.0485s
Retry: ticket_id=T0111, retry_number=1, wait=0.0450s
Retry: ticket_id=T0155, retry_number=1, wait=0.0475s
Retry: ticket_id=T0100, retry_number=1, wait=0.0481s
Retry: ticket_id=T0068, retry_number=1, wait=0.0541s
Retry: ticket_id=T0135, retry_number=1, wait=0.0556s
Retry: ticket_id=T0009, retry_number=1, wait=0.0517s
Retry: ticket_id=T0067, retry_number=1, wait=0.0478s
Retry: ticket_id=T0106, retry_number=1, wait=0.0562s
Retry: ticket_id=T0097, retry_number=1, wait=0.0521s
Retry: ticket_id=T0003, retry_number=1, wait=0.0485s
Retry: ticket_id=T0019, retry_number=1, wait=0.0470s
Retry: ticket_id=T0086, retry_number=1, wait=0.0501s
Retry: ticket_id=T0065, retry_number=1, wait=0.0463s

--- Task 4 Retry Summary ---
Eligible tickets: 156
Successful tickets: 156
Transient errors: 19
Recovered errors: 19
Permanent errors: 0

--- Task 5 Validation Summary ---
classified_json: 135
classified_keyword: 12
flagged_invalid_output: 9

Results saved to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\task4_retry_results.csv

Original category labels matched successfully.
ALL TASK 4 AND TASK 5 CHECKS PASSED

### Task 6: Compare Zero-Shot and Few-Shot Prompting
****************************************************
Script:compare_prompts.py

Both prompt strategies were evaluated on the same 156 eligible tickets, with no token budget applied. Accuracy was calculated against `true_category` for classified tickets only. Invalid outputs were routed to human review and excluded from the accuracy denominator.

| Metric                       | Zero-shot | Few-shot |
| ---------------------------- | --------: | -------: |
| Eligible tickets             |       156 |      156 |
| Tickets classified           |       147 |      147 |
| Correct predictions          |       126 |      147 |
| Accuracy                     |     85.7% |   100.0% |
| Total tokens                 |    15,796 |   29,680 |
| Tokens per classified ticket |    107.46 |   201.90 |
| Invalid/failed tickets       |         9 |        9 |
| Call failures                |         0 |        0 |

**Zero-shot confusion matrix** (rows = actual category; columns = predicted category):

| Actual \ Predicted | Billing | Delivery | Technical | Fraud |
| ------------------ | ------: | -------: | --------: | ----: |
| Billing            |      38 |        0 |         0 |     0 |
| Delivery           |       0 |       36 |         0 |     0 |
| Technical          |      10 |        0 |        29 |     0 |
| Fraud              |      11 |        0 |         0 |    23 |

Zero-shot prompting achieved 85.7% accuracy (126/147), while few-shot prompting achieved 100% accuracy (147/147), correcting 21 classification errors. Few-shot prompting used 13,884 additional tokens, increasing total token usage by approximately 87.9%. The extra tokens can be worthwhile for high-risk classifications, especially fraud, where incorrect routing can have significant consequences. Zero-shot prompting may be more economical for lower-risk use cases when the cost of errors is acceptable.

**Output files:**

* `outputs/task6_zero_shot_results.csv`
* `outputs/task6_few_shot_results.csv`

task 6 output
--- ZERO_SHOT RESULTS ---
Eligible tickets: 156
Tickets classified: 147
Correct predictions: 126
Accuracy: 85.7% (126/147)
Invalid/failed tickets: 9
Total tokens: 15796
Tokens per classified ticket: 107.46
Token measurement: actual_usage
Call failures: 0
Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\task6_zero_shot_results.csv

--- FEW_SHOT RESULTS ---
Eligible tickets: 156
Tickets classified: 147
Correct predictions: 147
Accuracy: 100.0% (147/147)
Invalid/failed tickets: 9
Total tokens: 29680
Tokens per classified ticket: 201.90
Token measurement: actual_usage
Call failures: 0
Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\task6_few_shot_results.csv

ZERO-SHOT CONFUSION MATRIX
Rows = true category; columns = predicted category
True / Predicted       billing    delivery   technical       fraud
billing                     38           0           0           0
delivery                     0          36           0           0
technical                   10           0          29           0
fraud                       11           0           0          23

--- COMPARISON ---
zero_shot: classified=147, accuracy=85.7%, total_tokens=15796, tokens/classified=107.46
few_shot: classified=147, accuracy=100.0%, total_tokens=29680, tokens/classified=201.90


### Token budget and routing

Document the budget demonstration, token counts, and final routing rules. Fraud routes to `security_team` with HIGH priority; premium customers route to `premium_desk` with HIGH priority; other valid tickets route to `support_queue` with NORMAL priority. Skipped, long, invalid, or budget-exhausted tickets go to `human_review`.

Task 7: Budget, Routing and Output:
*************************************************
Script:budget_routing.py

A. Token budget demonstration

The zero-shot pipeline was run with TOKEN_BUDGET = 6000. Before each model call, the pipeline checked the cumulative token usage and blocked additional calls once the running total reached or exceeded the budget. The run processed 164 input tickets, classified 57 tickets, used 6,067 actual tokens, and marked 96 tickets as budget_exhausted. These tickets were routed to human_review with NORMAL priority.

Output: outputs/triage_budget_demo.csv

B. Final few-shot triage

The few-shot pipeline was run with TOKEN_BUDGET = 100000. It classified 147 tickets, used 29,680 actual tokens, and had zero budget-exhausted tickets. The remaining 17 tickets were routed to human review.

Routing rules:

Tickets with status skipped_empty, flagged_long, flagged_invalid_output, or budget_exhausted are routed to human_review with NORMAL priority.
Other tickets classified as fraud are routed to security_team with HIGH priority.
Other tickets belonging to premium customers are routed to premium_desk with HIGH priority.
All remaining tickets are routed to support_queue with NORMAL priority.
Customers without a matching row in outputs/customer_segments.csv are treated as non-premium.

The final output contains ticket_id, customer_id, status, category, segment_name, priority, route, and tokens_used.

Output: outputs/triage_results.csv

task 7 output
--- ZERO-SHOT BUDGET DEMO PIPELINE ---
Eligible input tickets: 164
Tickets classified: 57
Total actual tokens used: 6067
Token budget: 6000
Budget-exhausted tickets: 96
Human-review tickets: 107
Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\triage_budget_demo.csv

--- FEW-SHOT FINAL TRIAGE PIPELINE ---
Eligible input tickets: 164
Tickets classified: 147
Total actual tokens used: 29680
Token budget: 100000
Budget-exhausted tickets: 0
Human-review tickets: 17
Saved: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\triage_results.csv

--- TASK 7 SUMMARY ---
Budget demo tokens used: 6067
Budget demo exhausted tickets: 96
Final run tokens used: 29680
Final run exhausted tickets: 0


*******************************************


## Part D — Policy Retrieval and Refund Agent
*************************************************
### Policy retrieval

- Load the 5 supplied policy documents.
- Chunk documents using 40-word chunks and 10-word overlap.
- Use TF-IDF and cosine similarity to retrieve the top 3 chunks.
- Explain how TF-IDF works and document retrieval evaluation, including the zero-overlap comparison and its limitations.
- Use the supplied offline mock LLM and restrict answers to retrieved policy context.

Reference chunk counts: 15 total; refund policy 4, delivery 3, escalation 3, payment 3, privacy 2. Reference evaluation: 12/12 expected documents retrieved in the top 3, 12/12 expected facts matched, and 2/2 fallback questions correctly identified.

### Refund agent and safety

Implement the required tools: `get_order`, `search_policy`, `calculate_refund`, `issue_refund`, and `escalate_to_human`.

- Only completed orders are eligible for refunds.
- Delivery later than 45 minutes qualifies for a full refund; 45 minutes or less qualifies for no refund.
- Refunds greater than INR 1,000 must be escalated rather than issued automatically.
- Enforce iteration, token, and timeout limits with safe human handoff.
- Save an execution checkpoint after each tool observation and demonstrate crash/resume without duplicate tool execution.
TAsk 1:Chunk the documents
***************************************

 

Task 1: Policy Document Chunking
*******************************************
Script:chunk_policies.py
Objective: Split the five policy documents into smaller text chunks for retrieval in the policy assistant.

Implementation:

Read the policy documents from data/policies/.

Split each document into chunks of 40 words, using an overlap of 10 words between consecutive chunks.

Move the starting position forward by 30 words for each new chunk.

Store each chunk's source filename and text, along with its chunk ID and word-position metadata.

Save the generated chunks to outputs/policy_chunks.csv.

output:
Chunks by policy:
delivery_policy.txt: 3
escalation_policy.txt: 3
payment_policy.txt: 3
privacy_policy.txt: 2
refund_policy.txt: 4

Total chunks: 15
Saved to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\policy_chunks.csv


Task 2: Vectorise and Retrieve
****************************************
Script: policy_retrieval.py
Objective: Convert policy chunks into TF-IDF vectors and retrieve the most relevant chunks for a query using cosine similarity.
Implementation:
•	Used scikit-learn's TfidfVectorizer() to fit and transform the policy chunk texts.
•	Transformed the query using the same fitted vectorizer.
•	Ranked chunks by cosine similarity and returned the top 3 results.
•	Each result includes the source filename, similarity score, and chunk text.
Test query: refund policy late delivery
Result: The top three retrieved chunks all came from refund_policy.txt, satisfying the assignment's reference check.
TF-IDF explanation: Term Frequency (TF) measures how often a term appears in a chunk, while Inverse Document Frequency (IDF) gives less weight to terms that appear across many chunks. One limitation is that TF-IDF relies on word overlap and may not recognise two differently worded sentences that express the same meaning.
Output file: outputs/policy_chunks.csv



output:

Query: refund policy late delivery

Top retrieved chunks:

Rank: 1
Source: refund_policy.txt
Score: 0.2719
Text: order is delivered in more than 45 minutes, the customer receives a full refund of the order amount. If a completed order is delivered in 45 minutes or less, no late-delivery refund is paid. Refunds up to INR 1000 are

Rank: 2
Source: refund_policy.txt
Score: 0.2514
Text: Refund Policy. A refund can be requested only for orders whose status is completed. Orders with status cancelled were never charged, so no refund applies to them. If a completed order is delivered in more than 45 minutes, the customer
Rank: 3
Source: refund_policy.txt
Score: 0.2454
Text: late-delivery refund is paid. Refunds up to INR 1000 are approved automatically by the support system. A refund above INR 1000 must be approved by a human support lead before money is returned. Approved refunds are credited to the original

Reference check passed: all top three chunks are from refund_policy.txt.


Task 3: Augment and Answer
*************************************************
Objective: Generate policy-based answers using retrieved policy chunks as context.
Script:policy_assisstant.py

Implementation:

Retrieved the top 3 relevant chunks using the retrieve(question, k=3) function from policy_retrieval.py.

Sent exactly two messages to mock_llm.chat: a system message containing POLICY ASSISTANT and a user message containing the retrieved context and question.

Instructed the assistant to answer only from the supplied policy context and to state when the information could not be found.

Returned the generated answer text and the source filenames used.
output:

Test question: What refund applies to a delivery delayed by more than 45 minutes?

Result: The assistant answered that a delivery taking more than 45 minutes qualifies for a full refund of the order amount.

Source used: refund_policy.txt

Output: The answer(question) function returns the answer text and a list of source filenames.

output:

Question: What refund applies to a delivery delayed by more than 45 minutes?

Answer:
order is delivered in more than 45 minutes, the customer receives a full refund of the order amount.

Sources used:
- refund_policy.txt

Task 4: Evaluate Retrieval and Grounding
*****************************************************
Script:evaluate_policy.py

Objective: Evaluate retrieval accuracy and answer grounding using the 14 questions in data/raw/policy_eval.csv: 12 answerable questions and 2 questions not covered by the policy documents.

Evaluation metrics:

Document retrieval: Whether expected_doc appears among the top 3 retrieved sources.

Answer grounding: Whether the generated answer contains the exact, case-sensitive expected_fact substring.

Fallback handling: Whether an unanswerable question receives an answer beginning with I could not find.

Results:

Metric

40-word chunks, 10-word overlap

40-word chunks, zero overlap

Expected document in top 3

Verify overlap-10 run

12/12

Expected fact present

Verify overlap-10 run

10/12

Correct fallback for unanswerable questions

Verify overlap-10 run

2/2

Zero-overlap failure analysis:

Delivery refund threshold: The question asks, “What delivery time makes a completed order eligible for a full refund?” The expected fact, more than 45 minutes, was absent from the generated answer. The answer only stated that the customer receives a full refund of the order amount.

Failed payment refund timing: The question asks, “How soon is money returned when a payment fails but is deducted?” The expected fact, 48 hours, was absent from the answer, which stated only that the amount is returned automatically.

These failures show that retrieving the correct document does not guarantee that the complete supporting fact is available in the retrieved context. With zero overlap, a rule can be split across chunk boundaries, leaving the model without the exact information needed to answer correctly.

Both unanswerable questions received the required fallback response beginning with I could not find.

Output files:

outputs/policy_eval_overlap10.csv

outputs/policy_eval_overlap0.csv

output:

Metric                              Result
----------------------------------  -------
Answerable: expected_doc in top 3  12/12
Answerable: expected_fact present  10/12
Unanswerable: correct fallback     2/2
Detailed results saved to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\policy_eval_overlap0.csv

Answerable questions that failed with zero overlap:

Question: What delivery time makes a completed order eligible for a full refund?
Expected document: refund_policy.txt
Retrieved sources: refund_policy.txt; refund_policy.txt; privacy_policy.txt
Expected fact: 'more than 45 minutes'
Generated answer: receives a full refund of the order amount.

Question: How soon is money returned when a payment fails but is deducted?
Expected document: payment_policy.txt
Retrieved sources: payment_policy.txt; refund_policy.txt; privacy_policy.txt
Expected fact: '48 hours'
Generated answer: If a payment fails but money is deducted, the amount is returned automatically
 
1000 must be approved by a human support lead before money is returned.

Task 5:Define tools and the toolmap
************************************************
Script: refund tools.py
Available tools:
- get_order : Read an order's status, amount, and delivery time from the database.
- search_policy : Retrieve the three most relevant policy chunks.
- calculate_refund : Calculate the full refund for a delivery taking more than 45 minutes; otherwise return zero.
- issue_refund : Record a simulated full refund for an eligible completed order when the amount is at most ₹1,000.
- escalate_to_human : Record a human-review escalation for an eligible completed order when the refund exceeds ₹1,000.

Test 1: Refund calculation
60 minutes: {'refund_inr': 500.0}
Exactly 45 minutes: {'refund_inr': 0.0}

Test 2: Order lookup
{'order_id': 'ORD-100001', 'status': 'completed', 'order_amount': 109.65, 'delivery_minutes': 20.0}

Test 3: Cancelled order ORD-100020
Order details: {'order_id': 'ORD-100020', 'status': 'cancelled', 'order_amount': 247.0, 'delivery_minutes': None}
Agent result: {'status': 'rejected', 'message': 'Order status is cancelled. Only completed orders can receive a refund.'}

Test 4: Full agent workflow
{'status': 'not_eligible', 'refund_inr': 0.0, 'message': 'Delivery took 45 minutes or less. No refund is due.'}

Test 5: Direct attempt to issue more than ₹1,000
{'error': 'delivery time does not qualify for a refund'}

Test 6: Ledger verification
Ledger path: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\refund_ledger.jsonl
Ledger exists: False

TEST 4: Find eligible completed orders
('ORD-100048', 'completed', 128.25, 65.0)
('ORD-100067', 'completed', 135.0, 59.0)
('ORD-100072', 'completed', 360.0, 70.0)
('ORD-100074', 'completed', 116.0, 46.0)
('ORD-100075', 'completed', 256.5, 50.0)
('ORD-100082', 'completed', 264.0, 52.0)
('ORD-100109', 'completed', 372.0, 50.0)
('ORD-100132', 'completed', 439.2, 62.0)
('ORD-100136', 'completed', 560.0, 68.0)
('ORD-100140', 'completed', 523.5, 53.0)

TEST 5: Test the agent workflow
Testing order: ORD-100048
Amount: 128.25
Delivery minutes: 65.0
Agent result: {'status': 'simulated_refund_recorded', 'refund_inr': 128.25, 'message': 'Simulated refund of ₹128.25 recorded.', 'ledger': {'success': True, 'simulated': True, 'tool_name': 'issue_refund', 'order_id': 'ORD-100048', 'refund_inr': 128.25, 'ledger_file': 'C:\\Users\\Mary Moses\\AIML\\instamart-customer-copilot\\outputs\\refund_ledger.jsonl'}}
PASS: Eligible refund recorded.

TEST 6: Check cancelled-order protection
{'status': 'rejected', 'message': 'Order status is cancelled. Only completed orders can receive a refund.'}
PASS: Cancelled order rejected.

TEST 7: Check ledger
Ledger path: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\refund_ledger.jsonl
Ledger exists: True
{'timestamp': '2026-10-29T05:18:55.851941+00:00', 'tool_name': 'issue_refund', 'order_id': 'ORD-100048', 'refund_inr': 128.25

Task 6: ReAct Agent Results
******************************
script:agent_runner.py
The ReAct agent executes tool calls iteratively, appends each tool observation to the conversation, and stops when the model returns a final answer or a configured limit is reached. Each scenario run is recorded in outputs/agent_runs.jsonl.

Scenario ID

Status

Refund amount (INR)

Model calls

Tokens used

S1

REFUND

128.25

5

1221

S2

REFUND

135.00

5

1221

S3

ESCALATE

1999.00

5

1208

S4

DENIED

0.00

4

853

S5

DENIED

0.00

3

523

S6

NOT_FOUND

0.00

2

196

S7

FALLBACK

N/A

6

3372

S1–S6 produced the expected outcomes. S7 reached the six-iteration limit and returned a human-review fallback. All runs remained within the configured 6000-token budget.

results are saved here:

outputs/agent_runs.jsonl

S1: status=REFUND, calls=5, tokens=1221
   REFUND: INR 128.25 issued.
S2: status=REFUND, calls=5, tokens=1221
   REFUND: INR 135.0 issued.
S3: status=ESCALATE, calls=5, tokens=1208
   ESCALATE: refund above INR 1000 sent to a human lead.
S4: status=DENIED, calls=4, tokens=853
   DENIED: delivery was within 45 minutes.
S5: status=DENIED, calls=3, tokens=523
   DENIED: only completed orders can be refunded.
S6: status=NOT_FOUND, calls=2, tokens=196
   NOT_FOUND: no such order.
S7: status=FALLBACK, calls=6, tokens=3372
   FALLBACK: maximum iterations reached; human review required.

Results appended to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\agent_runs.jsonl

Task 7 — Safe stopping and graceful fallback
***********************************************

script:agent_runner_updated.py
stop_safely_demo

The agent implements three safety limits:

Maximum iterations: S7 stops after six model calls without a final answer and returns FALLBACK_MAX_ITERATIONS. The observed run used 3,726 tokens.

Token limit: S1 was tested with token_limit=200. The cumulative token count reached 327, exceeding the limit, and the agent returned a human-handoff fallback. The over-limit response's requested tool must not be executed.

Timeout: S1 was tested with time_limit_seconds=0. The agent returned FALLBACK_TIMEOUT before the first model call, with zero calls, zero tokens, and zero completed steps.

All fallback responses preserve completed steps and include a human-handoff summary. Refund and escalation actions are simulated; no real refunds are issued
output:
Task 7 S1: status=REFUND, calls=5, tokens=1502
   REFUND: INR 128.25 issued.
S2: status=REFUND, calls=5, tokens=1502
   REFUND: INR 135.0 issued.
S3: status=ESCALATE, calls=5, tokens=1489
   ESCALATE: refund above INR 1000 sent to a human lead.
S4: status=DENIED, calls=4, tokens=1070
   DENIED: delivery was within 45 minutes.
S5: status=DENIED, calls=3, tokens=680
   DENIED: only completed orders can be refunded.
S6: status=NOT_FOUND, calls=2, tokens=297
   NOT_FOUND: no such order.
S7: status=FALLBACK_MAX_ITERATIONS, calls=6, tokens=3726
   Human review required: maximum iterations reached.

Results appended to: C:\Users\Mary Moses\AIML\instamart-customer-copilot\outputs\agent_runs.jsonl

Demo output
Tokens used: 327
Final answer: FALLBACK: token limit exceeded; human review required.
Completed steps: 1

=== TIMEOUT DEMO ===
Status: FALLBACK_TIMEOUT
LLM calls: 0
Tokens used: 0
Final answer: Human review required: time limit reached.
Completed steps: 0

Both Task 7 demos passed.

Task 8 — Checkpointing and Resuming After a Crash
***************************************************
script:make_run_resumable.py

Objective: Make the refund agent resumable by saving its state after every tool observation.

Implementation:

Checkpoints are saved in state/<run_id>.json.

Each checkpoint stores the run ID, scenario ID, full message history, tokens used, step number, tools executed, LLM call count, and completed steps.

The agent simulates a crash immediately after the second tool execution, after the checkpoint has been saved.

resume_agent(run_id) loads the saved state and continues without repeating completed tool executions.

S1 demonstration results:

Metric

Result

Run ID

S1-task8-resume-demo

Simulated crash

After tool execution 2

LLM calls

5

Tokens used

1466

Final status

REFUND

Final answer

REFUND: INR 128.25 issued.

Tools executed across the crash and resume, in order:

get_order — before the crash

search_policy — before the crash

calculate_refund — after resuming

issue_refund — after resuming

Validation: The exact expected tool sequence was verified, no completed tool was repeated, the final status was REFUND, and the final answer contained INR 128.25.

Output files:

state/S1-task8-resume-demo.json

state/S1-task8-resume-demo_result.json

The refund workflow uses simulated tools and data.
output

======================================================
TASK 8: RESUMABLE AGENT DEMONSTRATION
======================================================
Scenario: S1
Run ID: S1-task8-resume-demo

Executing tool: get_order
Checkpoint saved after tool #1
Executing tool: search_policy
Checkpoint saved after tool #2

=== SIMULATED CRASH ===
Simulated crash after tool #2. Checkpoint: C:\Users\Mary Moses\AIML\instamart-customer-copilot\state\S1-task8-resume-demo.json

Tools saved before crash: ['get_order', 'search_policy']
Saved step number: 2

=== RESUMING AGENT ===
Loaded checkpoint for S1-task8-resume-demo; completed tools: ['get_order', 'search_policy']
Executing tool: calculate_refund
Checkpoint saved after tool #3
Executing tool: issue_refund
Checkpoint saved after tool #4

=== FINAL RESULT ===
Status: REFUND
Final answer: REFUND: INR 128.25 issued.
LLM calls: 5
Tokens used: 1466

Tools executed across crash and resume:
1. get_order
2. search_policy
3. calculate_refund
4. issue_refund

Checkpoint file: C:\Users\Mary Moses\AIML\instamart-customer-copilot\state\S1-task8-resume-demo.json
Final result file: C:\Users\Mary Moses\AIML\instamart-customer-copilot\state\S1-task8-resume-demo_result.json
Task 8 resume test passed.


Task 9 — ReAct versus Plan-and-Execute
*************************************************
My ReAct agent makes multiple model calls because it observes each tool result before deciding the next action. The measured call counts were 5 for S1, 3 for S5, and 2 for S6. This allows adaptive decisions but may increase latency and token usage.

A plan-and-execute agent generates the entire step list in one model call, executes the plan, and replans only when an error occurs. It may reduce model calls and token usage for predictable workflows, although the initial plan may be longer and unexpected errors can require additional calls. Actual token savings must be measured.

ReAct handles unexpected observations, such as NOT_FOUND or a cancelled order, by examining the tool result and changing its next action. A plan-and-execute agent must validate tool results and replan if the original plan is no longer appropriate.

For this refund workflow, I would choose ReAct with safety checks and a token limit. Refund decisions depend on order status, policy eligibility, delivery time, and the calculated amount. Adapting to actual observations is more important than minimizing model calls alone. Checkpointing also allows the workflow to resume without repeating completed tools.

## Limitations and Next Steps

- All data is synthetic and does not represent actual customers or transactions.
- The supplied mock LLM is an offline simulation, not a production language model.
- Model scores and segment profiles are specific to the generated dataset.
- The retention list is illustrative/post-hoc because premium status is derived from full-window RFM.
- Future work could include real-world data validation, monitoring for data drift, stronger model evaluation, and production-grade access controls and audit logging.
