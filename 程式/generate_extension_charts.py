from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.font_manager import FontProperties
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    fbeta_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    cross_val_predict,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 42
DATA_PATH = Path("healthcare-dataset-stroke-data.csv")
OUTPUT_DIR = Path("extension_report_assets")

NAVY = "#2F455C"
NAVY_LIGHT = "#8FA8C3"
RED = "#E53935"
RED_DARK = "#B71C1C"
BLUE = "#3E6B8F"
GOLD = "#D9A441"
GRAY = "#697783"
LIGHT_GRAY = "#EEF2F5"
LIGHT_BLUE = "#E8EEF5"
WHITE = "#FFFFFF"

FONT_PATH = Path(r"C:\Windows\Fonts\msjh.ttc")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\msjhbd.ttc")
FONT = FontProperties(fname=FONT_PATH)
FONT_BOLD = FontProperties(fname=FONT_BOLD_PATH)


def configure_style():
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
            "grid.color": "#D9E1E8",
            "grid.alpha": 0.7,
            "axes.titleweight": "bold",
            "savefig.facecolor": WHITE,
            "savefig.bbox": "tight",
        }
    )


def title(ax, text, subtitle=None):
    ax.set_title(
        text,
        fontproperties=FONT_BOLD,
        fontsize=23,
        color=NAVY,
        loc="left",
        pad=20,
    )
    if subtitle:
        ax.text(
            0,
            1.01,
            subtitle,
            transform=ax.transAxes,
            fontproperties=FONT,
            fontsize=12,
            color=GRAY,
            va="bottom",
        )


def apply_font(ax, tick_size=11):
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FONT)
        label.set_fontsize(tick_size)
    ax.xaxis.label.set_fontproperties(FONT)
    ax.yaxis.label.set_fontproperties(FONT)


def save(fig, filename):
    fig.savefig(OUTPUT_DIR / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_pipeline(numeric_features, categorical_features):
    numeric_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        [
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )
    return Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "model",
                LogisticRegression(max_iter=3000, random_state=RANDOM_STATE),
            ),
        ]
    )


def class_weight_label(value):
    if value is None:
        return "None"
    if value == "balanced":
        return "balanced"
    return f"1:{value[1]}"


def run_experiment():
    data = pd.read_csv(DATA_PATH)
    X = data.drop(columns=["id", "stroke"])
    y = data["stroke"]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    numeric_features = X.select_dtypes(include="number").columns.tolist()
    categorical_features = X.select_dtypes(exclude="number").columns.tolist()
    pipeline = build_pipeline(numeric_features, categorical_features)

    search = GridSearchCV(
        pipeline,
        {
            "model__C": [0.01, 0.1, 1.0, 10.0, 100.0],
            "model__class_weight": [
                None,
                "balanced",
                {0: 1, 1: 3},
                {0: 1, 1: 5},
                {0: 1, 1: 10},
            ],
            "model__solver": ["liblinear", "lbfgs"],
        },
        scoring="average_precision",
        cv=StratifiedKFold(
            n_splits=5, shuffle=True, random_state=RANDOM_STATE
        ),
        n_jobs=1,
        refit=True,
    )
    search.fit(X_train, y_train)

    oof_probabilities = cross_val_predict(
        clone(search.best_estimator_),
        X_train,
        y_train,
        cv=StratifiedKFold(
            n_splits=5, shuffle=True, random_state=RANDOM_STATE + 1
        ),
        method="predict_proba",
        n_jobs=1,
    )[:, 1]

    precision, recall, thresholds = precision_recall_curve(
        y_train, oof_probabilities
    )
    f2 = (
        5
        * precision[:-1]
        * recall[:-1]
        / np.maximum(4 * precision[:-1] + recall[:-1], 1e-12)
    )
    best_index = int(np.argmax(f2))
    best_threshold = float(thresholds[best_index])

    final_model = clone(search.best_estimator_)
    final_model.fit(X_train, y_train)
    test_probabilities = final_model.predict_proba(X_test)[:, 1]
    default_predictions = (test_probabilities >= 0.5).astype(int)
    tuned_predictions = (test_probabilities >= best_threshold).astype(int)

    def metrics(predictions):
        return {
            "Accuracy": accuracy_score(y_test, predictions),
            "Precision": precision_score(
                y_test, predictions, zero_division=0
            ),
            "Recall": recall_score(y_test, predictions),
            "F1-score": f1_score(y_test, predictions, zero_division=0),
            "F2-score": fbeta_score(
                y_test, predictions, beta=2, zero_division=0
            ),
            "PR-AUC": average_precision_score(y_test, test_probabilities),
        }

    return {
        "search": search,
        "precision": precision,
        "recall": recall,
        "thresholds": thresholds,
        "f2": f2,
        "best_index": best_index,
        "best_threshold": best_threshold,
        "default_predictions": default_predictions,
        "tuned_predictions": tuned_predictions,
        "y_test": y_test,
        "default_metrics": metrics(default_predictions),
        "tuned_metrics": metrics(tuned_predictions),
    }


def chart_dataset_eda(data):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.6))

    counts = data["stroke"].value_counts().sort_index()
    bars = axes[0].bar(
        ["未中風", "中風"],
        counts.values,
        color=[NAVY_LIGHT, RED],
        width=0.62,
    )
    axes[0].bar_label(bars, fmt="%d", padding=4, fontsize=12)
    axes[0].set_ylabel("人數", fontproperties=FONT, fontsize=12)
    axes[0].set_title(
        "類別分布",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
    )

    sns.boxplot(
        data=data,
        x="stroke",
        y="age",
        hue="stroke",
        palette=[NAVY_LIGHT, RED],
        legend=False,
        ax=axes[1],
    )
    axes[1].set_xticks([0, 1], ["未中風", "中風"])
    axes[1].set_xlabel("")
    axes[1].set_ylabel("年齡", fontproperties=FONT, fontsize=12)
    axes[1].set_title(
        "年齡與中風",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
    )

    sns.boxplot(
        data=data,
        x="stroke",
        y="avg_glucose_level",
        hue="stroke",
        palette=[NAVY_LIGHT, RED],
        legend=False,
        ax=axes[2],
    )
    axes[2].set_xticks([0, 1], ["未中風", "中風"])
    axes[2].set_xlabel("")
    axes[2].set_ylabel("平均血糖值", fontproperties=FONT, fontsize=12)
    axes[2].set_title(
        "血糖與中風",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
    )

    for ax in axes:
        apply_font(ax)
        sns.despine(ax=ax)
    fig.suptitle(
        "Dataset 視覺化：類別不平衡與主要風險特徵",
        fontproperties=FONT_BOLD,
        fontsize=23,
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "資料共 5,110 筆；中風者僅 249 人（4.87%），且中風族群的年齡與血糖分布較高。",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=12,
        color=RED_DARK,
    )
    fig.subplots_adjust(
        left=0.06, right=0.98, top=0.82, bottom=0.18, wspace=0.30
    )
    save(fig, "00_dataset_eda.png")


def chart_correlation(data):
    columns = [
        "age",
        "hypertension",
        "heart_disease",
        "avg_glucose_level",
        "bmi",
        "stroke",
    ]
    labels = ["年齡", "高血壓", "心臟病", "平均血糖", "BMI", "中風"]
    corr = data[columns].corr()

    fig, ax = plt.subplots(figsize=(9.5, 7.2))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap=sns.diverging_palette(220, 15, as_cmap=True),
        vmin=-0.3,
        vmax=1,
        square=True,
        linewidths=1,
        linecolor=WHITE,
        cbar_kws={"shrink": 0.8},
        annot_kws={"fontsize": 11},
        ax=ax,
    )
    ax.set_xticklabels(labels, fontproperties=FONT, rotation=30, ha="right")
    ax.set_yticklabels(labels, fontproperties=FONT, rotation=0)
    title(
        ax,
        "相關性分析：數值特徵與中風",
        "相關性僅表示線性關聯，不代表因果關係。",
    )
    fig.text(
        0.5,
        0.015,
        "與 stroke 關聯較明顯：年齡 0.25、高血壓 0.13、心臟病 0.13、平均血糖 0.13",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=12,
        color=RED_DARK,
    )
    fig.subplots_adjust(left=0.13, right=0.92, top=0.84, bottom=0.18)
    save(fig, "00_correlation_heatmap.png")


def chart_preprocessing_summary(data):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.6))

    missing = data.isna().sum().sort_values(ascending=False)
    missing = missing[missing > 0]
    bars = axes[0].bar(
        ["BMI"], [int(missing.get("bmi", 0))], color=RED, width=0.55
    )
    axes[0].bar_label(bars, fmt="%d", padding=4, fontsize=13)
    axes[0].set_ylim(0, 230)
    axes[0].set_ylabel("缺失筆數", fontproperties=FONT, fontsize=12)
    axes[0].set_title(
        "Missing Value",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
    )
    axes[0].text(
        0.5,
        0.76,
        "以訓練資料中位數填補\n並放入 Pipeline",
        transform=axes[0].transAxes,
        ha="center",
        fontproperties=FONT,
        fontsize=11,
        color=NAVY,
    )

    axes[1].axis("off")
    axes[1].set_title(
        "One-Hot Encoding",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
        pad=14,
    )
    axes[1].text(
        0.5,
        0.67,
        "原始模型特徵\n10 欄",
        ha="center",
        va="center",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=WHITE,
        bbox={"boxstyle": "round,pad=0.8", "fc": NAVY, "ec": NAVY},
    )
    axes[1].annotate(
        "",
        xy=(0.72, 0.67),
        xytext=(0.28, 0.67),
        arrowprops={"arrowstyle": "->", "lw": 2.5, "color": RED},
    )
    axes[1].text(
        0.5,
        0.31,
        "轉換後模型特徵\n21 欄",
        ha="center",
        va="center",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
        bbox={
            "boxstyle": "round,pad=0.8",
            "fc": LIGHT_BLUE,
            "ec": NAVY,
        },
    )

    numeric = data[["age", "avg_glucose_level", "bmi"]].copy()
    numeric["bmi"] = numeric["bmi"].fillna(numeric["bmi"].median())
    standardized = (numeric - numeric.mean()) / numeric.std(ddof=0)
    positions = np.arange(3)
    before_ranges = numeric.max() - numeric.min()
    after_ranges = standardized.max() - standardized.min()
    axes[2].bar(
        positions - 0.18,
        before_ranges.values,
        0.36,
        label="標準化前範圍",
        color=NAVY_LIGHT,
    )
    axes[2].bar(
        positions + 0.18,
        after_ranges.values,
        0.36,
        label="StandardScaler 後範圍",
        color=RED,
    )
    axes[2].set_xticks(positions, ["Age", "Glucose", "BMI"])
    axes[2].set_ylabel("最大值－最小值", fontproperties=FONT, fontsize=11)
    axes[2].set_title(
        "Standardization",
        fontproperties=FONT_BOLD,
        fontsize=17,
        color=NAVY,
    )
    axes[2].legend(prop=FONT, fontsize=9)

    for ax in (axes[0], axes[2]):
        apply_font(ax)
        sns.despine(ax=ax)
    fig.suptitle(
        "資料前處理：缺失值、編碼轉換與標準化",
        fontproperties=FONT_BOLD,
        fontsize=23,
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.015,
        "所有前處理皆包在 Pipeline 內，交叉驗證時只使用各折訓練資料估計參數。",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=12,
        color=RED_DARK,
    )
    fig.subplots_adjust(
        left=0.06, right=0.98, top=0.82, bottom=0.18, wspace=0.32
    )
    save(fig, "00_preprocessing_summary.png")


def chart_grid_search(result):
    grid = pd.DataFrame(result["search"].cv_results_)
    grid["C"] = grid["param_model__C"].astype(float)
    grid["class_weight"] = grid["param_model__class_weight"].map(
        class_weight_label
    )
    grid["solver"] = grid["param_model__solver"].astype(str)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    order = ["None", "balanced", "1:3", "1:5", "1:10"]
    for ax, solver in zip(axes, ["liblinear", "lbfgs"]):
        pivot = (
            grid[grid["solver"] == solver]
            .pivot(index="class_weight", columns="C", values="mean_test_score")
            .reindex(order)
        )
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".3f",
            cmap=sns.light_palette(RED, as_cmap=True),
            vmin=grid["mean_test_score"].min(),
            vmax=grid["mean_test_score"].max(),
            linewidths=1,
            linecolor=WHITE,
            cbar=ax is axes[-1],
            ax=ax,
            annot_kws={"fontsize": 11},
        )
        ax.set_title(
            f"Solver：{solver}",
            fontproperties=FONT_BOLD,
            fontsize=17,
            color=NAVY,
            pad=12,
        )
        ax.set_xlabel("C（正則化強度的反比）", fontproperties=FONT, fontsize=12)
        ax.set_ylabel("class_weight", fontproperties=FONT, fontsize=12)
        apply_font(ax)

    fig.suptitle(
        "GridSearchCV：各參數組合的交叉驗證 PR-AUC",
        fontproperties=FONT_BOLD,
        fontsize=25,
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.025,
        "最佳組合：C=0.01、class_weight=1:5、solver=liblinear；CV PR-AUC=0.1958",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=13,
        color=RED_DARK,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "#FFF4F2",
            "edgecolor": RED,
            "linewidth": 1.2,
        },
    )
    fig.subplots_adjust(
        left=0.07, right=0.93, top=0.82, bottom=0.19, wspace=0.25
    )
    save(fig, "01_gridsearch_pr_auc_heatmap.png")


def chart_threshold_curve(result):
    thresholds = result["thresholds"]
    precision = result["precision"][:-1]
    recall = result["recall"][:-1]
    f2 = result["f2"]
    best = result["best_index"]
    best_threshold = result["best_threshold"]

    fig, ax = plt.subplots(figsize=(12, 6.75))
    ax.plot(thresholds, precision, color=BLUE, linewidth=3, label="Precision")
    ax.plot(thresholds, recall, color=RED, linewidth=3, label="Recall")
    ax.plot(thresholds, f2, color=GOLD, linewidth=3, label="F2-score")
    ax.axvline(
        best_threshold,
        color=NAVY,
        linestyle="--",
        linewidth=2.5,
        label=f"最佳 threshold = {best_threshold:.3f}",
    )
    ax.axvline(
        0.5,
        color=GRAY,
        linestyle=":",
        linewidth=2,
        label="預設 threshold = 0.5",
    )
    ax.scatter(
        [best_threshold],
        [f2[best]],
        color=GOLD,
        edgecolor=NAVY,
        linewidth=1.5,
        s=130,
        zorder=5,
    )
    ax.annotate(
        f"F2 最高點\nPrecision={precision[best]:.3f}\nRecall={recall[best]:.3f}",
        xy=(best_threshold, f2[best]),
        xytext=(best_threshold + 0.11, min(f2[best] + 0.16, 0.91)),
        arrowprops={"arrowstyle": "->", "color": NAVY, "lw": 1.5},
        bbox={"boxstyle": "round,pad=0.5", "fc": WHITE, "ec": RED, "lw": 1.5},
        fontproperties=FONT,
        fontsize=12,
        color=NAVY,
    )
    title(
        ax,
        "分類門檻調整：為什麼選擇 0.268？",
        "使用訓練集 Out-of-Fold 預測尋找 F2-score 最高點，測試集不參與門檻選擇。",
    )
    ax.set_xlabel("分類 threshold", fontproperties=FONT, fontsize=13)
    ax.set_ylabel("指標分數", fontproperties=FONT, fontsize=13)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(prop=FONT, loc="upper right", frameon=True)
    apply_font(ax)
    sns.despine(ax=ax)
    save(fig, "02_threshold_precision_recall_f2.png")


def chart_confusion_matrices(result):
    matrices = [
        confusion_matrix(result["y_test"], result["default_predictions"]),
        confusion_matrix(result["y_test"], result["tuned_predictions"]),
    ]
    labels = [
        "預設 threshold = 0.500",
        f"調整後 threshold = {result['best_threshold']:.3f}",
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.8))

    for ax, matrix, label in zip(axes, matrices, labels):
        sns.heatmap(
            matrix,
            annot=True,
            fmt="d",
            cmap=sns.light_palette(NAVY, as_cmap=True),
            cbar=False,
            square=True,
            linewidths=2,
            linecolor=WHITE,
            ax=ax,
            annot_kws={"fontsize": 25, "fontweight": "bold"},
        )
        ax.set_title(
            label,
            fontproperties=FONT_BOLD,
            fontsize=18,
            color=NAVY,
            pad=14,
        )
        ax.set_xlabel("模型預測", fontproperties=FONT, fontsize=13)
        ax.set_ylabel("實際結果", fontproperties=FONT, fontsize=13)
        ax.set_xticklabels(["未中風", "中風"], fontproperties=FONT)
        ax.set_yticklabels(
            ["未中風", "中風"], fontproperties=FONT, rotation=0
        )
    fig.suptitle(
        "分類門檻調整前後：混淆矩陣比較",
        fontproperties=FONT_BOLD,
        fontsize=25,
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.025,
        "TP：18 → 40｜FN：32 → 10｜FP：50 → 209",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=13,
        color=RED_DARK,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "#FFF4F2",
            "edgecolor": RED,
            "linewidth": 1.2,
        },
    )
    fig.subplots_adjust(
        left=0.08, right=0.97, top=0.82, bottom=0.18, wspace=0.28
    )
    save(fig, "03_confusion_matrix_comparison.png")


def chart_performance_tradeoff(result):
    metrics = ["Accuracy", "Precision", "Recall", "F1-score", "F2-score"]
    default_values = [result["default_metrics"][metric] for metric in metrics]
    tuned_values = [result["tuned_metrics"][metric] for metric in metrics]

    default_cm = confusion_matrix(
        result["y_test"], result["default_predictions"]
    )
    tuned_cm = confusion_matrix(result["y_test"], result["tuned_predictions"])
    error_names = ["TP 找出中風", "FN 漏判", "FP 誤警示"]
    default_errors = [default_cm[1, 1], default_cm[1, 0], default_cm[0, 1]]
    tuned_errors = [tuned_cm[1, 1], tuned_cm[1, 0], tuned_cm[0, 1]]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.8))

    x = np.arange(len(metrics))
    width = 0.35
    bars1 = axes[0].bar(
        x - width / 2,
        default_values,
        width,
        label="預設 0.500",
        color=NAVY_LIGHT,
    )
    bars2 = axes[0].bar(
        x + width / 2,
        tuned_values,
        width,
        label=f"調整後 {result['best_threshold']:.3f}",
        color=RED,
    )
    axes[0].bar_label(bars1, fmt="%.2f", padding=3, fontsize=11)
    axes[0].bar_label(bars2, fmt="%.2f", padding=3, fontsize=11)
    axes[0].set_xticks(x, metrics)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("分數", fontproperties=FONT, fontsize=12)
    axes[0].set_title(
        "核心評估指標",
        fontproperties=FONT_BOLD,
        fontsize=19,
        color=NAVY,
        pad=12,
    )
    axes[0].legend(prop=FONT, loc="upper center")
    apply_font(axes[0])

    x2 = np.arange(len(error_names))
    bars3 = axes[1].bar(
        x2 - width / 2,
        default_errors,
        width,
        label="預設 0.500",
        color=NAVY_LIGHT,
    )
    bars4 = axes[1].bar(
        x2 + width / 2,
        tuned_errors,
        width,
        label=f"調整後 {result['best_threshold']:.3f}",
        color=[RED, RED_DARK, GOLD],
    )
    axes[1].bar_label(bars3, padding=3, fontsize=11)
    axes[1].bar_label(bars4, padding=3, fontsize=11)
    axes[1].set_xticks(x2, error_names)
    axes[1].set_ylabel("測試集人數", fontproperties=FONT, fontsize=12)
    axes[1].set_title(
        "醫療篩檢的實際取捨",
        fontproperties=FONT_BOLD,
        fontsize=19,
        color=NAVY,
        pad=12,
    )
    axes[1].legend(prop=FONT, loc="upper left")
    apply_font(axes[1])

    fig.suptitle(
        "Threshold Tuning 結果：Recall 提升，但需接受更多誤警示",
        fontproperties=FONT_BOLD,
        fontsize=24,
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.025,
        "Recall：0.36 → 0.80｜FN：32 → 10｜Precision：0.26 → 0.16｜FP：50 → 209",
        ha="center",
        fontproperties=FONT_BOLD,
        fontsize=14,
        color=RED_DARK,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "#FFF4F2",
            "edgecolor": RED,
            "linewidth": 1.2,
        },
    )
    fig.subplots_adjust(
        left=0.07, right=0.98, top=0.82, bottom=0.20, wspace=0.12
    )
    save(fig, "04_performance_tradeoff.png")


def export_results(result):
    comparison = pd.DataFrame(
        [result["default_metrics"], result["tuned_metrics"]],
        index=["Default threshold", "Tuned threshold"],
    )
    comparison.insert(0, "Threshold", [0.5, result["best_threshold"]])
    comparison.to_csv(
        OUTPUT_DIR / "model_metric_comparison.csv",
        encoding="utf-8-sig",
    )

    default_cm = confusion_matrix(
        result["y_test"], result["default_predictions"]
    )
    tuned_cm = confusion_matrix(result["y_test"], result["tuned_predictions"])
    summary = (
        f"Best parameters: {result['search'].best_params_}\n"
        f"Best CV PR-AUC: {result['search'].best_score_:.4f}\n"
        f"Best OOF F2 threshold: {result['best_threshold']:.4f}\n"
        f"Default confusion matrix: {default_cm.tolist()}\n"
        f"Tuned confusion matrix: {tuned_cm.tolist()}\n"
        f"Default metrics: {result['default_metrics']}\n"
        f"Tuned metrics: {result['tuned_metrics']}\n"
    )
    (OUTPUT_DIR / "experiment_summary.txt").write_text(
        summary, encoding="utf-8"
    )


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    configure_style()
    data = pd.read_csv(DATA_PATH)
    chart_dataset_eda(data)
    chart_correlation(data)
    chart_preprocessing_summary(data)
    result = run_experiment()
    chart_grid_search(result)
    chart_threshold_curve(result)
    chart_confusion_matrices(result)
    chart_performance_tradeoff(result)
    export_results(result)
    print(f"Charts saved to: {OUTPUT_DIR.resolve()}")
    for path in sorted(OUTPUT_DIR.iterdir()):
        print(path.name)


if __name__ == "__main__":
    main()
