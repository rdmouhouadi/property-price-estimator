# Models: how they work, pros and cons, where to learn more

## Start here

- **An Introduction to Statistical Learning (ISLR)**, James, Witten, Hastie & Tibshirani. Free PDF with Python labs: https://www.statlearning.com. §6.2 covers Ridge; chapter 8 covers trees, random forests and boosting.
- **Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow**, Aurélien Géron. Chapter 4 covers linear models and regularization; chapters 6–7 cover trees and ensembles.
- **StatQuest with Josh Starmer** (YouTube): short visual explanations. Video titles are listed per model below.
- **Why trees win on tabular data:** Grinsztajn, Oyallon & Varoquaux (2022), *Why do tree-based models still outperform deep learning on typical tabular data?*, NeurIPS. https://arxiv.org/abs/2207.08815

## Results in this project

Validation, H2 2024, all sales, no DPE features (`reports/model_comparison.csv`):

| Model | Median error | Within 20% | Train time |
|---|---:|---:|---:|
| Baseline (neighbourhood average) | 19.9% | 50.2% | – |
| Ridge | 19.6% | 50.9% | 2 s |
| Random forest (300k rows) | 18.3% | 53.8% | 12 min |
| **LightGBM (1M rows)** | **17.5%** | **55.9%** | **28 s** |
| XGBoost (1M rows) | 17.6% | 55.7% | 75 s |

## Baseline: neighbourhood average

- **How it works:** no learning. Predict the past 12-month average price per m² of the cadastral section.
- **Why it's here:** the bar every model must beat. A model that can't beat it adds nothing.

## Ridge regression

- **How it works:** linear regression with an L2 penalty that shrinks large coefficients. Stable when features are correlated.
- **Pros:** very fast, interpretable coefficients, a strong reference.
- **Cons:** straight-line relationships only. It can't learn that a m² is worth more in Paris than in a village unless you build that interaction yourself. That's why it barely beat the baseline here.
- **Learn:** ISLR §6.2 · StatQuest *"Regularization Part 1: Ridge (L2) Regression"* · Hoerl & Kennard (1970), *Technometrics*.

## Random forest

- **How it works:** many deep decision trees, each trained on a random sample of rows and features, with predictions averaged ("bagging").
- **Pros:** robust, little tuning, rarely overfits badly.
- **Cons:** slow and memory-hungry on millions of rows (12 min for 300k rows here), large model files, usually below boosting in accuracy.
- **Learn:** ISLR §8.2.2 · StatQuest *"Random Forests Part 1 – Building, Using and Evaluating"* · Breiman (2001), *Random Forests*, Machine Learning 45(1).

## Gradient boosting (the principle behind LightGBM and XGBoost)

- **How it works:** trees are built **one after another**, each correcting the errors left by the previous ones. The learning rate sets the size of each correction.
- **Pros:** top accuracy on tabular data, handles missing values and mixed types.
- **Cons:** more hyperparameters, and it can overfit, so we use early stopping on validation.
- **Learn:** ISLR §8.2.3 · StatQuest *"Gradient Boost Part 1–4"* · Friedman (2001), *Greedy Function Approximation: A Gradient Boosting Machine*, Annals of Statistics.

## XGBoost

- **How it works:** gradient boosting with built-in regularization and many engineering optimizations.
- **Pros:** very accurate, mature, widely used in industry and competitions.
- **Cons:** slower than LightGBM on large data (75 s vs 28 s here).
- **Learn:** StatQuest *"XGBoost Part 1–4"* · Chen & Guestrin (2016), *XGBoost: A Scalable Tree Boosting System*, KDD. https://arxiv.org/abs/1603.02754

## LightGBM (chosen)

- **How it works:**
  - trees grow **leaf by leaf**, always splitting where the error drops most;
  - feature values are bucketed into histograms for speed;
  - categorical features are handled natively.
- **Pros:** fastest on large data, accurate, uses categories and missing values directly. That's how one model serves sales with and without a DPE.
- **Cons:** leaf-wise growth can overfit small datasets, so tune `num_leaves` and `min_child_samples`.
- **Settings used:** learning rate 0.05, 255 leaves, min 50 samples per leaf, 80% row and column subsampling, early stopping (100 rounds), 2,646 trees.
- **Learn:** docs https://lightgbm.readthedocs.io/en/latest/Features.html · Ke et al. (2017), *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*, NeurIPS.

## Permutation importance (feature selection)

- **How it works:** shuffle one feature on the validation set and measure how much the error grows.
- **Pros:** works for any model, measured on unseen data.
- **Cons:** misleading for **correlated features**: shuffle one, and its twin compensates. Our three market-price features are correlated, so the commune and département ones look weaker than they are.
- **Rule used:** drop a feature if its importance is ≈0 or below about 2× its standard deviation. Dropped here: `t_months` (trees can't extrapolate time), `month`, `dpe_genere_immeuble`.
- **Learn:** C. Molnar, *Interpretable Machine Learning* (free online): https://christophm.github.io/interpretable-ml-book/ · scikit-learn guide: https://scikit-learn.org/stable/modules/permutation_importance.html

## Explanations (planned for the app)

Per-prediction contributions use LightGBM's native TreeSHAP (`predict(..., pred_contrib=True)`), not the `shap` package ([ADR-0001](adr/0001-data-processing-stack.md)).
