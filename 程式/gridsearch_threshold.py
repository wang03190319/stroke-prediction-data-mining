#!/usr/bin/env python
# coding: utf-8

# # GridSearchCV 與 Threshold Tuning：MLP 神經網路最終版
# 
# 這份 notebook 是期末報告使用的神經網路主軸版本。它延續期中 `Stroke Prediction Dataset` 的資料清理、視覺化、Missing Value、Encoding、標準化與傳統 ML 模型比較，並在期末依課程要求加入神經網路。
# 
# 本版定位：
# 
# 1. **主模型**：`MLPClassifier` / `Multilayer Perceptron` / 多層感知器神經網路。
# 2. **方法**：`Pipeline` + `GridSearchCV` + `OOF F2 threshold tuning`。
# 3. **LR 角色**：`Logistic Regression` 只作為 `benchmark / baseline / 可解釋基準模型`，不是期末主模型。
# 4. **最終 MLP 結果**：threshold 約 `0.245`，Recall `0.78`，F2-score `0.4295`，PR-AUC `0.2736`，TP `39`，FN `11`，FP `215`。
# 
# > 注意：原本的 `extension_report_assets/02_threshold_precision_recall_f2.png` 是 LR benchmark 的 threshold 圖，最佳門檻約 `0.268`。本 notebook 會重新產生神經網路版本的 threshold 圖，避免和最終 MLP 主軸混用。
# 

# ## 1. 載入套件與設定
# 
# `RANDOM_STATE` 固定隨機結果，讓資料切分、交叉驗證與神經網路訓練可重現。
# 

# In[1]:


from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

RANDOM_STATE = 42
DATA_PATH = Path("healthcare-dataset-stroke-data.csv")
OUT_DIR = Path("neural_network_assets")
OUT_DIR.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid")
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ## 2. 讀取資料與切分訓練 / 測試集
# 
# - `id` 是識別碼，不作為模型特徵。
# - `stroke` 是二元目標欄位。
# - 使用 `stratify=y` 保持訓練集與測試集的中風比例，這對類別不平衡資料很重要。
# 

# In[2]:


df = pd.read_csv(DATA_PATH)

X = df.drop(columns=["id", "stroke"])
y = df["stroke"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=RANDOM_STATE,
)

print(f"Full dataset rows: {len(df)}")
print(f"Training rows: {len(X_train)}")
print(f"Test rows: {len(X_test)}")
print(f"Full stroke rate: {y.mean():.4f}")
print(f"Training stroke rate: {y_train.mean():.4f}")
print(f"Test stroke rate: {y_test.mean():.4f}")

df.head()


# ## 3. 建立前處理 Pipeline
# 
# 期中已做過 Missing Value、Encoding 與 Normalization。期末延伸版把這些前處理放進 `Pipeline`，讓每一折交叉驗證都只從該折訓練資料學習補值、編碼與標準化參數，降低資料洩漏風險。
# 
# - 數值欄位：中位數補值 + StandardScaler 標準化。
# - 類別欄位：眾數補值 + One-Hot Encoding。
# 

# In[3]:


numeric_features = [
    "age",
    "hypertension",
    "heart_disease",
    "avg_glucose_level",
    "bmi",
]
categorical_features = [
    "gender",
    "ever_married",
    "work_type",
    "Residence_type",
    "smoking_status",
]

numeric_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
)
categorical_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ]
)

print("Numeric features:", numeric_features)
print("Categorical features:", categorical_features)


# ## 4. 建立 MLPClassifier 神經網路主模型
# 
# 本期末主模型是 `MLPClassifier`，也就是多層感知器神經網路。這份資料是表格型資料，不是圖片或時間序列，因此使用 MLP 比 CNN / RNN 更適合。
# 
# 資料中中風個案非常少，所以使用 `sample_weight` 讓模型在訓練時更重視中風樣本。
# 

# In[4]:


sample_weight = compute_sample_weight(class_weight={0: 1, 1: 5}, y=y_train)

pipeline = Pipeline(
    steps=[
        ("preprocess", preprocessor),
        (
            "model",
            MLPClassifier(
                max_iter=800,
                early_stopping=True,
                n_iter_no_change=25,
                random_state=RANDOM_STATE,
            ),
        ),
    ]
)

pipeline


# ## 5. 使用 GridSearchCV 搜尋 MLP 參數
# 
# `GridSearchCV` 用來搜尋神經網路設定。模型選擇指標使用 `average_precision`，也就是 PR-AUC，因為中風資料高度不平衡，PR-AUC 比 Accuracy 更能反映少數類別的風險排序能力。
# 
# 最終報告採用的最佳參數為：
# 
# - `hidden_layer_sizes = (64,)`
# - `activation = relu`
# - `alpha = 0.0001`
# - `learning_rate_init = 0.001`
# 

# In[5]:


param_grid = {
    "model__hidden_layer_sizes": [(32,), (64,), (32, 16)],
    "model__alpha": [0.0001, 0.001],
    "model__learning_rate_init": [0.001, 0.0005],
    "model__activation": ["relu"],
}

cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)

search = GridSearchCV(
    estimator=pipeline,
    param_grid=param_grid,
    scoring="average_precision",
    cv=cv,
    n_jobs=1,
    refit=True,
    return_train_score=False,
)

search.fit(X_train, y_train, model__sample_weight=sample_weight)

print("Best NN parameters:")
print(search.best_params_)
print(f"Best NN CV PR-AUC: {search.best_score_:.4f}")


# ## 6. 用 OOF 預測機率調整 threshold
# 
# 預設情況下，模型通常以 `0.5` 作為分類門檻。但中風篩檢較重視不要漏掉真正高風險者，因此本研究使用 F2-score 選擇較重視 Recall 的門檻。
# 
# 不能直接用測試集找 threshold，否則測試集就不再是公平的最終評估。這裡使用訓練集的 Out-of-Fold（OOF）預測：每筆訓練資料的機率，都由沒有看過該筆資料的模型產生。
# 

# In[6]:


threshold_cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=RANDOM_STATE + 2,
)

best_pipeline = search.best_estimator_

oof_probabilities = cross_val_predict(
    best_pipeline,
    X_train,
    y_train,
    cv=threshold_cv,
    method="predict_proba",
    n_jobs=1,
    params={"model__sample_weight": sample_weight},
)[:, 1]

print("First 10 OOF probabilities:")
print(np.round(oof_probabilities[:10], 4))


# ## 7. 尋找 F2-score 最高的神經網路 threshold
# 
# F2-score 比 F1-score 更重視 Recall：
# 
# \[
# F_2 = \frac{5 \times Precision \times Recall}{4 \times Precision + Recall}
# \]
# 
# 本研究使用訓練集 OOF 預測找出 F2-score 最高的門檻。最終 MLP threshold 約為 `0.245`。
# 

# In[7]:


def threshold_curve(y_true, probabilities):
    thresholds = np.linspace(0.02, 0.98, 300)
    rows = []
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        rows.append(
            {
                "threshold": threshold,
                "precision": precision_score(y_true, predictions, zero_division=0),
                "recall": recall_score(y_true, predictions, zero_division=0),
                "f2": fbeta_score(y_true, predictions, beta=2, zero_division=0),
            }
        )
    return pd.DataFrame(rows)


curve = threshold_curve(y_train, oof_probabilities)
best_idx = curve["f2"].idxmax()
threshold_result = curve.loc[best_idx].to_dict()

pd.Series(threshold_result).round(4)


# ### 圖表：MLP Precision、Recall 與 F2-score 的門檻變化
# 
# 下圖是神經網路 MLP 的 threshold tuning 圖，不是 LR 的 `0.268` 圖。
# 

# In[8]:


fig, ax = plt.subplots(figsize=(11, 6))
ax.plot(curve["threshold"], curve["precision"], label="Precision", linewidth=2.8)
ax.plot(curve["threshold"], curve["recall"], label="Recall", linewidth=2.8)
ax.plot(curve["threshold"], curve["f2"], label="F2-score", linewidth=2.8)
ax.axvline(threshold_result["threshold"], color="#E4473D", linestyle="--", linewidth=2.2, label=f"Best threshold = {threshold_result['threshold']:.3f}")
ax.axvline(0.5, color="#687786", linestyle=":", linewidth=2.2, label="Default threshold = 0.5")
ax.scatter([threshold_result["threshold"]], [threshold_result["f2"]], color="#E4473D", s=80, zorder=5)
ax.set_title("MLP Neural Network：Precision / Recall / F2-score threshold curve", fontsize=16, weight="bold")
ax.set_xlabel("Classification threshold")
ax.set_ylabel("Score")
ax.set_ylim(0, 1.02)
ax.legend(loc="best")
ax.grid(True, alpha=0.28)
fig.tight_layout()
fig.savefig(OUT_DIR / "02_nn_threshold_precision_recall_f2.png", dpi=180)
plt.show()

print(f"Saved to: {OUT_DIR / '02_nn_threshold_precision_recall_f2.png'}")


# **圖表解讀：**
# 
# - threshold 越低，模型越容易判定為中風，Recall 通常會提高。
# - threshold 降低雖然能找出更多真正中風個案，但 Precision 會下降，代表誤報增加。
# - F2-score 比 F1-score 更重視 Recall，最高點對應的 MLP threshold 約為 `0.245`。
# - 門檻只使用訓練集 OOF 預測決定，測試集沒有參與選擇，可避免資料洩漏。
# 
# **八分鐘報告講法：**  
# 預設門檻 0.5 不一定適合醫療篩檢，因此本研究使用 OOF F2-score，在重視 Recall 的前提下替 MLP 神經網路選出約 0.245 的門檻。
# 

# ## 8. 在未碰過的測試集進行最終評估
# 
# 測試集只在所有模型參數與 threshold 決定後才使用。PR-AUC 與 ROC-AUC 只依賴預測機率排序，不會因單一 threshold 改變；Accuracy、Precision、Recall、F1、F2 與混淆矩陣則會隨 threshold 改變。
# 

# In[9]:


def metric_row(y_true, probabilities, threshold):
    predictions = (probabilities >= threshold).astype(int)
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, predictions),
        "precision": precision_score(y_true, predictions, zero_division=0),
        "recall": recall_score(y_true, predictions, zero_division=0),
        "f1": f1_score(y_true, predictions, zero_division=0),
        "f2": fbeta_score(y_true, predictions, beta=2, zero_division=0),
        "pr_auc": average_precision_score(y_true, probabilities),
        "roc_auc": roc_auc_score(y_true, probabilities),
        "tp": int(((y_true == 1) & (predictions == 1)).sum()),
        "fn": int(((y_true == 1) & (predictions == 0)).sum()),
        "fp": int(((y_true == 0) & (predictions == 1)).sum()),
        "tn": int(((y_true == 0) & (predictions == 0)).sum()),
    }, predictions


best_pipeline.fit(X_train, y_train, model__sample_weight=sample_weight)
test_probabilities = best_pipeline.predict_proba(X_test)[:, 1]

default_metrics, default_predictions = metric_row(y_test, test_probabilities, threshold=0.5)
tuned_metrics, tuned_predictions = metric_row(
    y_test,
    test_probabilities,
    threshold=threshold_result["threshold"],
)

comparison = pd.DataFrame(
    [default_metrics, tuned_metrics],
    index=["Default threshold", "Tuned threshold"],
)

comparison.round(4)


# ## 9. 混淆矩陣與分類報告
# 
# 最終 MLP tuned threshold 結果應與報告一致：
# 
# - threshold 約 `0.245`
# - Recall `0.78`
# - F2-score `0.4295`
# - PR-AUC `0.2736`
# - TP `39`
# - FN `11`
# - FP `215`
# 

# In[10]:


default_cm = confusion_matrix(y_test, default_predictions)
tuned_cm = confusion_matrix(y_test, tuned_predictions)

print("Default threshold confusion matrix:")
print(default_cm)
print("\nTuned threshold confusion matrix:")
print(tuned_cm)
print("\nTuned threshold classification report:")
print(classification_report(y_test, tuned_predictions, digits=4, zero_division=0))


# ### 圖表：MLP 調整後 threshold 的混淆矩陣
# 

# In[11]:


fig, ax = plt.subplots(figsize=(6.2, 5.8))
sns.heatmap(
    tuned_cm,
    annot=True,
    fmt="d",
    cmap="Blues",
    cbar=False,
    ax=ax,
    annot_kws={"fontsize": 20, "weight": "bold"},
)
ax.set_title(f"MLP Neural Network tuned threshold\nthreshold={threshold_result['threshold']:.3f}", fontsize=15, weight="bold")
ax.set_xlabel("Predicted label")
ax.set_ylabel("True label")
ax.set_xticklabels(["No stroke", "Stroke"])
ax.set_yticklabels(["No stroke", "Stroke"], rotation=0)
fig.tight_layout()
fig.savefig(OUT_DIR / "06_neural_network_confusion_matrix.png", dpi=180)
plt.show()

print(f"Saved to: {OUT_DIR / '06_neural_network_confusion_matrix.png'}")


# ## 10. 與 Logistic Regression benchmark 比較
# 
# LR benchmark 只作為比較基準，不是期末主模型。
# 
# | 模型定位 | threshold | Recall | F2-score | PR-AUC | FN | FP |
# |---|---:|---:|---:|---:|---:|---:|
# | MLP 主模型 | 0.245 | 0.78 | 0.4295 | 0.2736 | 11 | 215 |
# | LR benchmark | 0.268 | 0.80 | 0.4454 | 0.2517 | 10 | 209 |
# 
# 解讀：MLP 的 PR-AUC 高於 LR benchmark，代表風險排序能力有提升；但 Recall / F2 略低於 LR benchmark，因此不能說神經網路全面勝過 LR。
# 

# In[12]:


lr_benchmark = {
    "model": "LR benchmark + threshold",
    "threshold": 0.2680144223928285,
    "precision": 0.1606425702811245,
    "recall": 0.8,
    "f1": 0.26755852842809363,
    "f2": 0.44543429844098,
    "pr_auc": 0.25171238326186424,
    "fp": 209,
    "fn": 10,
    "tp": 40,
}

mlp_final = {
    "model": "MLP main model + threshold",
    "threshold": tuned_metrics["threshold"],
    "precision": tuned_metrics["precision"],
    "recall": tuned_metrics["recall"],
    "f1": tuned_metrics["f1"],
    "f2": tuned_metrics["f2"],
    "pr_auc": tuned_metrics["pr_auc"],
    "fp": tuned_metrics["fp"],
    "fn": tuned_metrics["fn"],
    "tp": tuned_metrics["tp"],
}

model_comparison = pd.DataFrame([mlp_final, lr_benchmark])
model_comparison.round(4)


# ## 11. 最終結論
# 
# 本 notebook 的最終定位如下：
# 
# - 期中：使用 LR / RF / KNN 建立傳統 ML 基線。
# - 期末：依老師要求加入 Neural Network，並以 MLPClassifier 作為主模型。
# - 方法：Pipeline + GridSearchCV + OOF F2 threshold tuning。
# - 結果：MLP 在 PR-AUC 上高於 LR benchmark，代表風險排序能力有提升。
# - 限制：MLP 的 Recall / F2 略低於 LR，因此不能說神經網路全面勝過 LR。
# - 結論：本研究是從期中報告延伸而來的神經網路主軸研究，LR 只是比較基準。
# 
