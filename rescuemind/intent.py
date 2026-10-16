"""Transparent ML intent recognizer, keyword baseline, optional pretrained embeddings.

The TF-IDF + logistic-regression model trains on small embedded synthetic samples.
It is NOT a validated Japanese NLU system; compare with the held-out tests.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

TRAIN = {
    "water": [
        "水を避難所Bへ届けて", "飲料水が必要です", "給水物資の配送をお願いします",
        "喉が渇いている人に飲み物を配って", "ペットボトルを運んで",
        "飲み水を届けてほしい", "水分補給できるものを届ける", "水を優先してください",
        "脱水対策の物資を急いで", "飲料が足りません", "喉の渇きを癒したい",
        "給水車の代わりに飲み物を運んで", "飲水を補充してください",
        "清潔な水が不足しています", "水分の確保を優先して",
        "給水ポイントから配送して", "飲み物の供給をお願いします",
        "避難所に水の備蓄がありません", "お茶ではなく水を届けて",
        "ペットボトルの飲料水を輸送して",
    ],
    "medicine": [
        "薬を避難所Bへ届けて", "医薬品を至急配送して", "包帯が不足しています",
        "救急箱を運んで", "医療物資の補充をお願いします", "治療に必要な道具を届けて",
        "けが人がいるので応急処置用品が必要", "消毒液を運んで",
        "医療用の備品を優先して", "救急用品を配送してください",
        "負傷者向けの物資を届ける", "包帯とガーゼを配って",
        "応急手当に必要なものがない", "薬品が切れました",
        "傷を手当てするための物資が必要です", "医療キットを運んで",
        "救護所へ衛生材料を補充して", "絆創膏を届けて",
        "止血用ガーゼがありません", "痛み止めを運んでください",
    ],
}

# Unseen examples: never train on these. Stated as a small illustrative test set.
HELD_OUT = [
    ("避難者が飲むものを求めています", "water"),
    ("水のボトルを優先して搬送して", "water"),
    ("熱中症予防のために飲み物を配達", "water"),
    ("喉の渇いた人が多くいます", "water"),
    ("給水を最優先で対応してください", "water"),
    ("けがをした人の手当に使う品が必要", "medicine"),
    ("救護のための医薬品を運んで", "medicine"),
    ("負傷者への治療物資を補充", "medicine"),
    ("消毒や処置に使う用具を届けて", "medicine"),
    ("救急搬送チームに包帯を送って", "medicine"),
]

PROTOTYPES = {
    "water": ["飲料水、水分、給水、飲み物、喉が渇く、水を運ぶ", "water drinking supply"],
    "medicine": ["医療物資、包帯、救急箱、薬、応急処置用品、けが人", "medicine first aid supply"],
}

@dataclass(frozen=True)
class Intent:
    item: str
    shelter: str
    confidence: float
    classifier: str


def parse_shelter(text: str) -> str:
    m = re.search(r"(?:避難所|シェルター|shelter)\s*([ABＡＢ])", text, flags=re.I)
    return m.group(1).translate(str.maketrans("ＡＢ", "AB")).upper() if m else "B"


class IntentClassifier:
    def __init__(self, mode: str = "tfidf", model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        if mode not in ("tfidf", "keyword", "minilm"):
            raise ValueError(f"Unknown mode: {mode}")
        self.mode = mode
        self.model_name = model_name
        if mode == "tfidf":
            from sklearn.pipeline import Pipeline
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            self.model = Pipeline([
                ("vectorizer", TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)),
                ("classifier", LogisticRegression(C=5, random_state=42, max_iter=1000)),
            ])
            self.model.fit([x for label in TRAIN for x in TRAIN[label]],
                           [label for label in TRAIN for _ in TRAIN[label]])
        elif mode == "minilm":
            from sentence_transformers import SentenceTransformer
            import numpy as np
            self.np = np
            self.model = SentenceTransformer(model_name)
            self.labels = ["water", "medicine"]
            self.embeddings = self.model.encode(
                ["。".join(PROTOTYPES[name]) for name in self.labels],
                normalize_embeddings=True,
            )

    def classify(self, text: str) -> Intent:
        if not text.strip():
            raise ValueError("Instruction must not be empty")
        if self.mode == "tfidf":
            probs = self.model.predict_proba([text])[0]
            idx = int(probs.argmax())
            label = str(self.model.classes_[idx])
            conf = float(probs[idx])
        elif self.mode == "minilm":
            emb = self.model.encode([text], normalize_embeddings=True)[0]
            scores = self.embeddings @ emb
            idx = int(scores.argmax())
            label = self.labels[idx]
            # Cosine similarity is a score, NOT a calibrated probability.
            conf = float(scores[idx])
        else:
            kw = {
                "water": ("水", "飲", "喉", "給水", "脱水", "熱中症", "ペットボトル"),
                "medicine": ("医", "薬", "包帯", "救", "けが", "負傷", "消毒", "手当", "治療", "止血"),
            }
            counts = {k: sum(v in text for v in words) for k, words in kw.items()}
            label = "water" if counts["water"] >= counts["medicine"] else "medicine"
            conf = 1.0 if max(counts.values()) > 0 else 0.0
        return Intent(label, parse_shelter(text), conf, self.mode)
