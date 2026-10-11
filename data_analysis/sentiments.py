"""Analyse de sentiments avec VADER, indépendante de Django.

VADER attribue à chaque mot connu une valeur (« excellent » = +2.7, « murder » = -3.7),
tient compte des négations, des majuscules et de la ponctuation, puis résume le
texte par un score « compound » entre -1 (très négatif) et +1 (très positif).
VADER ne comprend que l'anglais : les autres langues sont détectées et mises de côté.
"""
import re

import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DetectorFactory.seed = 0  # langdetect est aléatoire : on fixe la graine pour des résultats reproductibles
ANALYSEUR = SentimentIntensityAnalyzer()  # chargé une seule fois, au démarrage
SEUIL = 0.05  # seuil recommandé par les auteurs de VADER


def detecter_langue(texte):
    try:
        return detect(texte)
    except LangDetectException:  # texte trop court ou sans lettres
        return None


def etiquette(score):
    if score >= SEUIL:
        return "positive"
    if score <= -SEUIL:
        return "negative"
    return "neutral"


def mots_influents(texte, n=3):
    """Les n mots du texte qui pèsent le plus dans le score, avec leur valeur dans le lexique."""
    mots = re.findall(r"[a-z']+", texte.lower())
    valeurs = {mot: ANALYSEUR.lexicon[mot] for mot in mots if mot in ANALYSEUR.lexicon}
    plus_forts = sorted(valeurs.items(), key=lambda paire: abs(paire[1]), reverse=True)[:n]
    return ", ".join(f"{mot} ({valeur:+.1f})" for mot, valeur in plus_forts)


def analyser_texte(texte):
    """Analyse un texte : langue, score, étiquette et mots déterminants."""
    if not isinstance(texte, str) or not texte.strip():
        return {"text": "", "lang": None, "label": "missing", "score": None, "mots": ""}
    langue = detecter_langue(texte)
    if langue != "en":
        return {"text": texte, "lang": langue, "label": "ignored", "score": None, "mots": ""}
    score = ANALYSEUR.polarity_scores(texte)["compound"]
    return {"text": texte, "lang": langue, "label": etiquette(score), "score": score, "mots": mots_influents(texte)}


def analyser_textes(textes):
    return [analyser_texte(texte) for texte in textes]


def enrichir(df, colonne):
    """Ajoute au DataFrame les colonnes langue, sentiment_score et sentiment."""
    resultats = analyser_textes(df[colonne].tolist())
    df = df.copy()
    df["langue"] = [r["lang"] for r in resultats]
    df["sentiment_score"] = [r["score"] for r in resultats]
    df["sentiment"] = [r["label"] if r["score"] is not None else None for r in resultats]
    return df, resultats


def resume(resultats):
    """Comptes et pourcentages, calculés sur les seuls textes réellement analysés."""
    analyses = [r for r in resultats if r["score"] is not None]
    total = len(analyses)

    def part(n):
        return round(100 * n / total) if total else 0

    positifs = sum(r["label"] == "positive" for r in analyses)
    neutres = sum(r["label"] == "neutral" for r in analyses)
    negatifs = sum(r["label"] == "negative" for r in analyses)
    scores = pd.Series([r["score"] for r in analyses], dtype="float64")
    return {
        "total": total,
        "positive": positifs, "neutral": neutres, "negative": negatifs,
        "positive_pct": part(positifs), "neutral_pct": part(neutres), "negative_pct": part(negatifs),
        "mean_score": round(scores.mean(), 2) if total else None,
        "median_score": round(scores.median(), 2) if total else None,
        "ignored": sum(r["label"] == "ignored" for r in resultats),
        "missing": sum(r["label"] == "missing" for r in resultats),
    }
