#!/usr/bin/env python
"""加入 sklearn MLPClassifier 神經網路，作為期末延伸模型比較。"""

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


def build_preprocessor():
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

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )


def find_best_f2_threshold(y_true, probabilities):
    thresholds = np.linspace(0.02, 0.98, 300)
    rows = []
    for threshold in thresholds:
        pred = (probabilities >= threshold).astype(int)
        rows.append(
            {
                "threshold": threshold,
                "precision": precision_score(y_true, pred, zero_division=0),
                "recall": recall_score(y_true, pred, zero_division=0),
                "f2": fbeta_score(y_true, pred, beta=2, zero_division=0),
            }
        )
    result = pd.DataFrame(rows)
    return result.iloc[result["f2"].idxmax()].to_dict()


def metric_row(y_true, probabilities, threshold):
    pred = (probabilities >= threshold).astype(int)
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "f2": fbeta_score(y_true, pred, beta=2, zero_division=0),
        "pr_auc": average_precision_score(y_true, probabilities),
        "roc_auc": roc_auc_score(y_true, probabilities),
        "confusion_matrix": confusion_matrix(y_true, pred),
    }, pred


def main():
    OUT_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    X = df.drop(columns=["stroke", "id"])
    y = df["stroke"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    sample_weight = compute_sample_weight(class_weight={0: 1, 1: 5}, y=y_train)
    pipeline = Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
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

    param_grid = {
        "model__hidden_layer_sizes": [(32,), (64,), (32, 16)],
        "model__alpha": [0.0001, 0.001],
        "model__learning_rate_init": [0.001, 0.0005],
        "model__activation": ["relu"],
    }
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        pipeline,
        param_grid=param_grid,
        scoring="average_precision",
        cv=cv,
        n_jobs=1,
        refit=True,
    )
    search.fit(X_train, y_train, model__sample_weight=sample_weight)

    best_pipeline = search.best_estimator_
    threshold_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE + 2)
    oof_prob = cross_val_predict(
        best_pipeline,
        X_train,
        y_train,
        cv=threshold_cv,
        method="predict_proba",
        n_jobs=1,
        params={"model__sample_weight": sample_weight},
    )[:, 1]
    threshold_result = find_best_f2_threshold(y_train, oof_prob)

    best_pipeline.fit(X_train, y_train, model__sample_weight=sample_weight)
    test_prob = best_pipeline.predict_proba(X_test)[:, 1]
    default_metrics, _ = metric_row(y_test, test_prob, 0.5)
    tuned_metrics, tuned_pred = metric_row(y_test, test_prob, threshold_result["threshold"])

    lr_tuned = {
        "model": "LR + GridSearch + threshold",
        "threshold": 0.2680144223928285,
        "accuracy": 0.7857142857142857,
        "precision": 0.1606425702811245,
        "recall": 0.8,
        "f1": 0.26755852842809363,
        "f2": 0.44543429844098,
        "pr_auc": 0.25171238326186424,
        "roc_auc": 0.8387,
        "fp": 209,
        "fn": 10,
        "tp": 40,
    }
    nn_tuned = {
        "model": "Neural Network + threshold",
        **{k: v for k, v in tuned_metrics.items() if k != "confusion_matrix"},
        "fp": int(tuned_metrics["confusion_matrix"][0, 1]),
        "fn": int(tuned_metrics["confusion_matrix"][1, 0]),
        "tp": int(tuned_metrics["confusion_matrix"][1, 1]),
    }
    comparison = pd.DataFrame([lr_tuned, nn_tuned])
    comparison.to_csv(OUT_DIR / "nn_model_comparison.csv", index=False)

    summary = "\n".join(
        [
            f"Best NN parameters: {search.best_params_}",
            f"Best NN CV PR-AUC: {search.best_score_:.4f}",
            f"Best NN OOF F2 threshold: {threshold_result['threshold']:.4f}",
            f"NN default confusion matrix: {default_metrics['confusion_matrix'].tolist()}",
            f"NN tuned confusion matrix: {tuned_metrics['confusion_matrix'].tolist()}",
            "NN tuned metrics: "
            + str({k: v for k, v in tuned_metrics.items() if k != "confusion_matrix"}),
        ]
    )
    (OUT_DIR / "nn_experiment_summary.txt").write_text(summary, encoding="utf-8")

    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    metrics = ["precision", "recall", "f1", "f2", "pr_auc"]
    labels = ["Precision", "Recall", "F1", "F2", "PR-AUC"]
    x = np.arange(len(metrics))
    width = 0.36
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.bar(x - width / 2, [lr_tuned[m] for m in metrics], width, label="LR tuned", color="#8FA9C1")
    ax.bar(x + width / 2, [nn_tuned[m] for m in metrics], width, label="NN tuned", color="#E4473D")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 0.9)
    ax.set_ylabel("Score")
    ax.set_title("Logistic Regression 與 Neural Network 測試集比較", fontsize=18, weight="bold")
    for i, metric in enumerate(metrics):
        for dx, value in [(-width / 2, lr_tuned[metric]), (width / 2, nn_tuned[metric])]:
            ax.text(i + dx, value + 0.02, f"{value:.2f}", ha="center", fontsize=10)
    ax.legend()
    fig.text(
        0.5,
        0.02,
        f"NN threshold={threshold_result['threshold']:.3f}｜"
        f"NN confusion matrix={tuned_metrics['confusion_matrix'].tolist()}",
        ha="center",
        fontsize=11,
        color="#E4473D",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(OUT_DIR / "05_neural_network_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 5.8))
    sns.heatmap(
        tuned_metrics["confusion_matrix"],
        annot=True,
        fmt="d",
        cmap="Blues",
        cbar=False,
        ax=ax,
        annot_kws={"fontsize": 20, "weight": "bold"},
    )
    ax.set_title(f"Neural Network 調整門檻後\nthreshold={threshold_result['threshold']:.3f}", fontsize=16, weight="bold")
    ax.set_xlabel("模型預測")
    ax.set_ylabel("實際結果")
    ax.set_xticklabels(["未中風", "中風"])
    ax.set_yticklabels(["未中風", "中風"], rotation=0)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "06_neural_network_confusion_matrix.png", dpi=180)
    plt.close(fig)

    print(summary)
    print("\nComparison:")
    print(comparison.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
