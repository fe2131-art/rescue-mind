"""Fail-closed mission instruction policy for a two-category prototype.

This is a pre-departure sanity guard, NOT a calibrated safety classifier.
Jev remains mandatory to approve the on-site second leg in live missions.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import re
from .intent import IntentClassifier, Intent

WATER = re.compile(r'(飲料水|給水|水分|水(?!準|平|道)|飲み水|飲み物|ペットボトル|脱水|のど|喉|飲料)')
MEDICINE = re.compile(r'(医療|医薬|救急|応急|薬|包帯|絆創膏|ガーゼ|負傷|けが|怪我|治療|消毒|止血)')
UNSUPPORTED = re.compile(r'(?:避難所|シェルター|shelter)\s*([AC-ZＡＣ-Ｚ])', flags=re.I)

@dataclass(frozen=True)
class IntentGate:
    allow: bool
    reason: str
    intent: Intent


def decide_intent(text: str, classifier: IntentClassifier | None = None,
                  min_confidence: float = 0.60) -> IntentGate:
    """Avoid silent default selection for unclear, multi-supply, or unsupported sites.

    TF-IDF scores from 40 synthetic examples are NOT calibrated probabilities;
    this threshold is heuristic and must be evaluated with new user utterances.
    """
    if not (0.5 <= min_confidence <= 0.95) or not math.isfinite(min_confidence):
        raise ValueError('invalid mission-intent confidence threshold')
    c = classifier or IntentClassifier('tfidf')
    intent = c.classify(text)
    matches_water = bool(WATER.search(text))
    matches_medicine = bool(MEDICINE.search(text))
    explicit = (matches_water, matches_medicine)
    if intent.shelter != 'B' or UNSUPPORTED.search(text):
        reason = 'unsupported_shelter'
    elif all(explicit):
        reason = 'ambiguous_multiple_supplies'
    elif not any(explicit) and intent.confidence < min_confidence:
        reason = 'unknown_supply_request'
    elif not (math.isfinite(intent.confidence) and intent.confidence >= min_confidence):
        reason = 'low_nlu_score'
    elif matches_water and intent.item != 'water':
        reason = 'intent_keyword_conflict'
    elif matches_medicine and intent.item != 'medicine':
        reason = 'intent_keyword_conflict'
    else:
        reason = 'intent_accepted'
    return IntentGate(reason == 'intent_accepted', reason, intent)
