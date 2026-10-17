"""Two classic text classifiers in plain numpy (no scikit-learn): the baselines a fine-tune must beat.

Features are **hashed** word 1–2-grams plus character 3-grams inside words (robust to typos and to Spanish
inflections), log-scaled and L2-normalised. :class:`NaiveBayes` is multinomial naive Bayes; :class:`LogReg`
is softmax regression trained with full-batch gradient descent (Adam) and L2. Both give probabilities,
which the router (Lesson 14.03) needs to decide when to escalate.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence

import numpy as np

__all__ = ["featurize", "NaiveBayes", "LogReg", "DIM"]

DIM = 2**14
_WORD = re.compile(r"[a-záéíóúñü0-9$]+", re.I)


def _tokens(text: str) -> list[str]:
    words = _WORD.findall(text.lower())
    feats = [f"w:{w}" for w in words] + [f"b:{a}_{b}" for a, b in zip(words, words[1:])]
    for w in words:
        padded = f"<{w}>"
        feats += [f"c:{padded[i:i + 3]}" for i in range(len(padded) - 2)]
    return feats


def featurize(texts: Sequence[str], dim: int = DIM) -> np.ndarray:
    """``(n, dim)`` float32 matrix of hashed, log-scaled, L2-normalised counts (deterministic across runs)."""
    x = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for tok in _tokens(text):
            x[i, zlib.crc32(tok.encode()) % dim] += 1.0
    np.log1p(x, out=x)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.where(norms == 0, 1, norms)


class _Base:
    classes: list[str]

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - overridden
        raise NotImplementedError

    def predict(self, texts: Sequence[str]) -> list[tuple[str, float]]:
        """``[(label, confidence), ...]`` where confidence is the top class probability."""
        p = self.predict_proba(texts)
        return [(self.classes[j], float(p[i, j])) for i, j in enumerate(p.argmax(axis=1))]


class NaiveBayes(_Base):
    """Multinomial naive Bayes with Laplace smoothing ``alpha``."""

    def __init__(self, alpha: float = 0.1) -> None:
        self.alpha = alpha

    def fit(self, texts: Sequence[str], labels: Sequence[str]) -> NaiveBayes:
        self.classes = sorted(set(labels))
        x, y = featurize(texts), np.array([self.classes.index(l) for l in labels])
        counts = np.stack([x[y == k].sum(axis=0) for k in range(len(self.classes))]) + self.alpha
        self.log_prob = np.log(counts / counts.sum(axis=1, keepdims=True))
        self.log_prior = np.log(np.bincount(y, minlength=len(self.classes)) / len(y))
        return self

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray:
        z = featurize(texts) @ self.log_prob.T + self.log_prior
        z = np.exp(z - z.max(axis=1, keepdims=True))
        return z / z.sum(axis=1, keepdims=True)


class LogReg(_Base):
    """Softmax regression: ``epochs`` of full-batch Adam with learning rate ``lr`` and L2 penalty ``l2``."""

    def __init__(self, l2: float = 1e-4, lr: float = 0.5, epochs: int = 200, seed: int = 0) -> None:
        self.l2, self.lr, self.epochs, self.seed = l2, lr, epochs, seed

    def fit(self, texts: Sequence[str], labels: Sequence[str]) -> LogReg:
        self.classes = sorted(set(labels))
        x = featurize(texts)
        y = np.eye(len(self.classes), dtype=np.float32)[[self.classes.index(l) for l in labels]]
        w = np.zeros((x.shape[1], y.shape[1]), dtype=np.float32)
        b = np.zeros(y.shape[1], dtype=np.float32)
        m = [np.zeros_like(w), np.zeros_like(b)]
        v = [np.zeros_like(w), np.zeros_like(b)]
        for t in range(1, self.epochs + 1):
            z = x @ w + b
            p = np.exp(z - z.max(axis=1, keepdims=True))
            p /= p.sum(axis=1, keepdims=True)
            grads = [x.T @ (p - y) / len(x) + self.l2 * w, (p - y).mean(axis=0)]
            for i, (param, g) in enumerate(zip((w, b), grads)):
                m[i] = 0.9 * m[i] + 0.1 * g
                v[i] = 0.999 * v[i] + 0.001 * g * g
                param -= self.lr * (m[i] / (1 - 0.9**t)) / (np.sqrt(v[i] / (1 - 0.999**t)) + 1e-8)
        self.w, self.b = w, b
        return self

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray:
        z = featurize(texts) @ self.w + self.b
        p = np.exp(z - z.max(axis=1, keepdims=True))
        return p / p.sum(axis=1, keepdims=True)
