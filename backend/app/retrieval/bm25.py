import math
import re
from collections import Counter
from dataclasses import dataclass

from app.domain.event import Event


TOKEN_PATTERN = re.compile(
    r"[a-zA-Z0-9_]+|"
    r"[\u4e00-\u9fff\u3040-\u30ffー]+"
)


def tokenize(text: str) -> list[str]:
    """
    BM25 使用的轻量 tokenizer。

    英文 / 数字：
        按连续 token 保留。

    中文 / 日文：
        同时生成 unigram + bigram，
        避免依赖外部分词库。
    """

    tokens: list[str] = []

    for chunk in TOKEN_PATTERN.findall(
        text.lower()
    ):
        if chunk.isascii():
            tokens.append(chunk)
            continue

        characters = list(chunk)

        tokens.extend(
            characters
        )

        tokens.extend(
            chunk[index:index + 2]
            for index in range(
                len(chunk) - 1
            )
        )

    return tokens


@dataclass(
    frozen=True
)
class BM25SearchResult:
    event: Event
    score: float


class BM25EventRetriever:
    def __init__(
        self,
        events: list[Event],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError(
                "k1 must be > 0"
            )

        if not (
            0.0 <= b <= 1.0
        ):
            raise ValueError(
                "b must be between 0 and 1"
            )

        self.events = list(events)
        self.k1 = k1
        self.b = b

        self.documents = [
            tokenize(
                event.semantic_text
            )
            for event in self.events
        ]

        self.term_frequencies = [
            Counter(document)
            for document in self.documents
        ]

        self.document_lengths = [
            len(document)
            for document in self.documents
        ]

        self.average_document_length = (
            sum(
                self.document_lengths
            )
            / len(self.document_lengths)
            if self.document_lengths
            else 0.0
        )

        self.document_frequency = (
            self._build_document_frequency()
        )

    def _build_document_frequency(
        self,
    ) -> Counter[str]:
        frequency: Counter[str] = (
            Counter()
        )

        for document in self.documents:
            frequency.update(
                set(document)
            )

        return frequency

    def _idf(
        self,
        term: str,
    ) -> float:
        document_count = len(
            self.documents
        )

        frequency = (
            self.document_frequency.get(
                term,
                0,
            )
        )

        return math.log(
            1.0
            + (
                document_count
                - frequency
                + 0.5
            )
            / (
                frequency
                + 0.5
            )
        )

    def _score_document(
        self,
        query_tokens: list[str],
        document_index: int,
    ) -> float:
        if not self.documents:
            return 0.0

        term_frequency = (
            self.term_frequencies[
                document_index
            ]
        )

        document_length = (
            self.document_lengths[
                document_index
            ]
        )

        score = 0.0

        for term in set(
            query_tokens
        ):
            frequency = (
                term_frequency.get(
                    term,
                    0,
                )
            )

            if frequency == 0:
                continue

            normalization = (
                1.0
                - self.b
                + self.b
                * (
                    document_length
                    / self.average_document_length
                )
                if self.average_document_length
                else 1.0
            )

            numerator = (
                frequency
                * (
                    self.k1
                    + 1.0
                )
            )

            denominator = (
                frequency
                + self.k1
                * normalization
            )

            score += (
                self._idf(term)
                * numerator
                / denominator
            )

        return score

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
    ) -> list[BM25SearchResult]:
        if top_k < 1:
            raise ValueError(
                "top_k must be >= 1"
            )

        query_tokens = tokenize(
            query.strip()
        )

        if (
            not query_tokens
            or not self.events
        ):
            return []

        results = [
            BM25SearchResult(
                event=event,
                score=self._score_document(
                    query_tokens,
                    index,
                ),
            )
            for index, event
            in enumerate(self.events)
        ]

        results = [
            result
            for result in results
            if result.score > 0.0
        ]

        results.sort(
            key=lambda result: (
                -result.score,
                result.event.id,
            )
        )

        return results[:top_k]