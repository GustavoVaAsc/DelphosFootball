# Data Mining Project: System for Identifying Undervalued Football Players

**National Autonomous University of Mexico | Faculty of Engineering**
**Course:** Data Mining
**Professor:** M.Sc. Gerardo Gabriel Carrasco Zúñiga
**Semester:** 2027-1 | **Group:** 1
**Team Members:**
* Jiménez Ayala Yordi Josué
* Valenzuela Ascencio Gustavo

**Delivery Date (Draft/Proposal):** 09/30/2026

---

## 1. General Objective

Develop a data mining system through the application of the KDD process for the identification of economically undervalued football players, by integrating descriptive and predictive models that contrast athletic performance against their market valuation.

## 2. Project Context

The project relies on the **'Football Data from Transfermarkt'** dataset available on Kaggle, which consolidates multidimensional on-pitch performance metrics and historical transfer records.

In the business environment of sports analytics (*Front-Office Analytics*), the ability to detect financial inefficiencies is critical for optimizing human talent assets. This allows clubs to mitigate financial risks by avoiding overpaying due to subjective biases or media pressure, thereby maximizing the value of their investments through strictly data-driven decisions.

## 3. Strategy (KDD Process)

The KDD (*Knowledge Discovery in Databases*) methodology will be applied, structured in the following operational phases:

1. **Business domain understanding:** Definition of financial and athletic success metrics.
2. **Identification of relevant data:** Selection of key attributes in the dataset that directly impact performance and economic value.
3. **Data cleaning:** Exhaustive treatment of null values, outliers, and noise in the databases.
4. **Data transformation:** Feature engineering for normalization, scaling, and adaptation of variables to mathematical models.

## 4. Modeling Methodology

The modeling phase is oriented toward selecting and applying analytical techniques capable of discovering hidden patterns and predictive relationships in football performance data. A hybrid architecture is established:

### 4.1 Implementation of Data Mining Algorithms

Three fundamental approaches are distinguished within the implementation:

* **Descriptive models (Unsupervised learning):**
  Justification of the **K-Means** algorithm to discover real player archetypes. The algorithm groups athletes with similarities across multiple physical and tactical performance dimensions, overcoming the limitations of traditional positional labels (e.g., a defensive midfielder with playmaker statistics). This segmentation allows identifying player profiles with similar characteristics that can be fairly compared from an economic standpoint.

* **Predictive models (Supervised learning) - Regression:**
  Implementation of two complementary approaches to predict a player's "fair" economic value:
  * *Multiple Linear Regression:* Base model establishing a linear relationship between multiple performance statistics and the current market price.
  * *Polynomial Regression:* Advanced model designed to capture non-linear relationships and exponential growth effects (typical in the valuation of elite players).

* **Classification models (Experimentation):**
  Implementation of a binary classification model to categorize players into groups such as *'Undervalued/Profitable'* vs. *'Overvalued'*. **Random Forest** and **Decision Trees** will be tested to identify discrete patterns that can be used as quick decision criteria, complementing the predictive approach based on numerical regression.

## 5. Expectations

The system seeks to solve the problem of overpricing in the sports market.
* It is expected to statistically prove the existence of monetary inefficiencies in transfers.
* It is projected to generate a tool capable of providing recommendations of at least **3 profitable replacements for each evaluated elite asset**, guaranteeing an equivalence in athletic performance at a lower cost.

## 6. Work Plan (Baseline vs. Actual)

To guarantee the success and traceability of the project, the following schedule is established:

* **Weeks 1-2:** Business understanding and data selection.
* **Weeks 3-4:** Data cleaning and transformation.
* **Weeks 5-6:** Implementation of algorithms (K-means, Multiple Linear Regression, Polynomial Regression, and Random Forest/Decision Tree Classification).
* **Week 7:** Data interpretation and evaluation (Prediction Performance, Cross-validation, and Comparison of data mining schemes).
* **Week 8:** Comparison of results (Baseline vs. Actual) and final documentation (APA 7th edition format).

## 7. Tools and Environment

* Centralized development in the **Python** environment.
* Use of specialized libraries (such as Scikit-Learn and Pandas) for data manipulation and data mining algorithm implementation.

---

## EXTRAS THAT CAN BE DONE IF TIME PERMITS

**1. AI-Generated Scouting Reports (Human-Centered AI)**
Data analysis usually outputs tables of cold numbers that directors do not always know how to interpret. A language model (either by connecting the Gemini API or running a lightweight local model like Qwen in GGUF format) can be integrated to translate the mathematical results of the K-Means model into natural language.
* **Added value:** Instead of just showing that "Player B belongs to Cluster 4", the system would automatically draft a report: *"The signing of Player B is suggested. He shares a 92% statistical similarity in key passes and recoveries with the targeted star, but his market value is 65% lower, minimizing financial risk."*

**2. Private Scouting Processing with Local Models (GGUF Format)**
In elite football, recruitment strategies are strictly confidential information. A massive commercial differentiator is ensuring that the data mining model's discoveries never leave the club's servers. To achieve this, the generation of analytical reports can be executed offline by implementing a local language model in Windows environments. Using quantized files in GGUF format (e.g., agile iterations like the 8B-parameter Qwen), the system can read the metrics processed in Python and draft signing suggestions without relying on third-party APIs, demonstrating absolute control over architecture and data privacy.

---
**Core References:**
* Cariboo, D. (2024). *Football Data from Transfermarkt*. Kaggle.
* Faculty of Engineering, UNAM. (2026). *Syllabus MD Data Mining Course Syllabus*.
* Carrasco, G. G. (2026). *Introduction to the KDD Process; Clustering Algorithms; Predictive Models and Model Evaluation*. Class notes.