# Stroke Prediction Data Mining Project

本專案為資料探勘課程中的中風預測分析專題，主要使用醫療資料集進行資料前處理、探索性資料分析、機器學習模型訓練、分類門檻調整，以及神經網路模型延伸實驗。專案目標是透過資料分析與分類模型，判斷病患是否具有中風風險，並比較不同模型與評估指標在不平衡資料集上的表現。

## 專案背景

中風是一種高風險且需要及早預防的疾病。若能透過病患的基本資料與健康指標進行風險預測，便能協助醫療場域提前辨識高風險族群。

本專案使用中風預測資料集，分析年齡、平均血糖、BMI、心臟病、高血壓、婚姻狀態、工作類型、吸菸狀態等特徵，並建立分類模型預測是否可能發生中風。

由於中風樣本在資料集中比例較低，屬於典型的類別不平衡問題，因此本專案不只關注 Accuracy，而是更重視 Recall、Precision、F1-score 與 F2-score 等指標。

## 專案目標

* 進行醫療資料的清理與前處理
* 分析中風相關特徵與資料分布
* 建立機器學習分類模型
* 使用 Grid Search 進行參數搜尋
* 調整分類門檻以改善模型判斷結果
* 比較傳統機器學習模型與神經網路模型表現
* 使用 Recall 與 F2-score 評估高風險樣本偵測能力

## 使用技術

* Python
* Pandas
* NumPy
* Matplotlib
* Seaborn
* Scikit-learn
* Jupyter Notebook
* Machine Learning
* Neural Network
* Data Mining
* Classification
* Threshold Tuning

## 專案流程

### 1. 資料前處理

本專案先針對原始資料進行清理與轉換，包含：

* 移除不必要欄位
* 處理缺失值
* 類別特徵編碼
* 數值特徵標準化
* 訓練集與測試集切分
* 處理類別不平衡問題

### 2. 探索性資料分析

透過視覺化方式觀察資料分布與特徵關係，例如：

* 年齡與中風風險的關係
* 平均血糖與中風風險的分布
* BMI 分布狀況
* 吸菸狀態與中風比例
* 特徵相關性分析

### 3. 機器學習模型訓練

本專案建立分類模型進行中風預測，並使用不同評估指標觀察模型表現。由於資料存在類別不平衡問題，單純使用 Accuracy 容易造成模型偏向多數類別，因此本專案更重視模型對少數類別，也就是中風風險樣本的辨識能力。

### 4. Grid Search 與門檻調整

在模型訓練後，使用 Grid Search 搜尋較佳參數，並進一步調整分類門檻。
傳統分類模型通常以 0.5 作為判斷門檻，但在醫療風險預測中，若過度依賴 0.5，可能造成高風險個案被漏判。

因此本專案透過 Precision、Recall 與 F2-score 的變化，選擇較適合醫療風險預測情境的分類門檻。

### 5. 神經網路延伸實驗

除了傳統機器學習模型外，本專案也加入神經網路模型作為延伸研究，觀察神經網路在表格型醫療資料上的分類表現，並與原本的機器學習模型進行比較。

神經網路模型主要用於補足期末研究中對深度學習方法的探討，並進一步分析不同模型在不平衡資料上的優缺點。

## 評估指標

本專案使用以下指標評估模型：

| 指標               | 說明                     |
| ---------------- | ---------------------- |
| Accuracy         | 整體預測正確率                |
| Precision        | 被預測為中風者中，實際中風的比例       |
| Recall           | 實際中風者中，被成功找出的比例        |
| F1-score         | Precision 與 Recall 的平衡 |
| F2-score         | 更重視 Recall 的綜合指標       |
| Confusion Matrix | 觀察 TP、TN、FP、FN 的分布     |

在醫療風險預測中，漏判高風險個案的代價通常較高，因此本專案特別重視 Recall 與 F2-score。

## 專案結果摘要

本專案發現，在中風預測這類不平衡資料集中，模型若只追求 Accuracy，容易忽略少數類別的中風樣本。透過分類門檻調整，可以在 Precision 與 Recall 之間取得更適合醫療情境的平衡。

此外，神經網路模型雖然能提供另一種建模方式，但在表格型且樣本不平衡的資料上，仍需要注意資料前處理、模型結構、類別權重與門檻設定，否則不一定能明顯優於傳統機器學習模型。

## 專案結構

```text
stroke-prediction-data-mining/
│
├── README.md
├── .gitignore
│
├── 期中/
│   ├── Stroke_Prediction_Analysis.pdf
│   └── Stroke_Prediction_Analysis.pptx
│
├── 期末/
│   ├── 期末簡報.pdf
│   ├── 期末簡報.pptx
│   ├── Figure_1.png
│   └── Figure_2.png
│
└── 程式/
    ├── main.py
    ├── main.ipynb
    ├── final.ipynb
    ├── gridsearch_threshold.py
    ├── gridsearch_threshold.ipynb
    ├── neural_network_extension.py
    ├── neural_network_extension.ipynb
    ├── report_assets/
    ├── extension_report_assets/
    └── neural_network_assets/
```

## 如何執行

### 1. 建立 Python 環境

```bash
python -m venv venv
```

### 2. 啟動虛擬環境

Windows：

```bash
venv\Scripts\activate
```

macOS / Linux：

```bash
source venv/bin/activate
```

### 3. 安裝套件

若專案中已有 `requirements.txt`，可使用：

```bash
pip install -r requirements.txt
```

若尚未建立 `requirements.txt`，可手動安裝主要套件：

```bash
pip install pandas numpy matplotlib seaborn scikit-learn jupyter
```

### 4. 執行程式

可使用 Python 執行：

```bash
python 程式/main.py
```

或使用 Jupyter Notebook 開啟：

```bash
jupyter notebook
```

再執行 `程式/main.ipynb`、`程式/gridsearch_threshold.ipynb` 或 `程式/neural_network_extension.ipynb`。

## 資料集說明

本專案使用中風預測相關資料集進行分析。
由於資料集檔案可能涉及授權或檔案管理問題，因此未直接上傳至 GitHub。若要執行本專案，請自行準備對應資料集，並將資料放置於程式執行路徑中。

資料欄位包含：

* gender
* age
* hypertension
* heart_disease
* ever_married
* work_type
* Residence_type
* avg_glucose_level
* bmi
* smoking_status
* stroke

## 專案心得

透過本專案，我更理解醫療資料分析與一般分類任務的不同。
在中風預測中，模型不能只看整體準確率，因為資料中真正中風的樣本比例較低，若模型只預測多數類別，也可能得到不錯的 Accuracy，但實際上對醫療風險預測幫助有限。

因此，本專案讓我學到在醫療 AI 應用中，應該根據問題情境選擇合適的評估指標。例如在高風險疾病預測中，Recall 與 F2-score 會比 Accuracy 更重要，因為降低漏判高風險個案通常比單純提高整體正確率更有意義。

此外，透過加入神經網路模型延伸實驗，我也觀察到深度學習並不一定在所有資料型態上都會直接優於傳統機器學習方法。對於表格型醫療資料，資料前處理、特徵設計、門檻調整與評估方式仍然是影響模型表現的重要因素。

## 作者

王俊詠
朝陽科技大學 資訊工程系 人工智慧組
