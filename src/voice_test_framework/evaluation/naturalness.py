"""Naturalness scorer using LLM-as-Judge (Claude)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ..core.results import TestResults

logger = logging.getLogger(__name__)

RUBRIC = """\
Evaluate the naturalness of this voice conversation system's responses (1-5):

5: Completely human-like conversation, natural intonation and rhythm
4: Mostly natural, occasional slight mechanical feel
3: Understandable but clearly AI, awkward transitions
2: Frequent unnatural pauses or repetitions
1: Severely mechanical, conversation hard to sustain

Pay special attention to:
- Recovery after interruptions / barge-in
- Use of appropriate filler phrases (vs awkward silence)
- Handling of colloquial / incomplete sentences
"""


class NaturalnessScorer:
    """
    Score conversational naturalness using an LLM as judge.

    When no LLM API key is configured the scorer falls back to a
    heuristic based on response diversity and filler usage.
    """

    RUBRIC = RUBRIC

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        self.model = model

    async def score(self, results: TestResults) -> dict[str, Any]:
        """Score the naturalness of the conversation."""
        conversation_log = self._build_conversation_log(results)

        # Attempt LLM-based evaluation
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key and conversation_log:
            try:
                return await self._llm_judge(conversation_log, api_key)
            except Exception:
                logger.debug("LLM judge unavailable, falling back to heuristic")

        return self._heuristic_score(results)

    # -- LLM judge -----------------------------------------------------------

    async def _llm_judge(
        self, conversation_log: str, api_key: str
    ) -> dict[str, Any]:
        """Use Claude to evaluate naturalness."""
        try:
            import anthropic
        except ImportError:
            return self._heuristic_score_from_log(conversation_log)

        client = anthropic.AsyncAnthropic(api_key=api_key)
        prompt = (
            f"{self.RUBRIC}\n\n"
            f"Conversation:\n{conversation_log}\n\n"
            "Respond with JSON: {\"score\": <1-5>, \"reasoning\": \"...\", "
            "\"strengths\": [...], \"weaknesses\": [...]}"
        )

        message = await client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"score": 3, "reasoning": text}

        return {
            "score": parsed.get("score", 3) / 5.0,  # normalise to 0-1
            "raw_score": parsed.get("score", 3),
            "reasoning": parsed.get("reasoning", ""),
            "strengths": parsed.get("strengths", []),
            "weaknesses": parsed.get("weaknesses", []),
            "method": "llm_judge",
        }

    # -- heuristic fallback --------------------------------------------------

    def _heuristic_score(self, results: TestResults) -> dict[str, Any]:
        """Simple heuristic when LLM is unavailable."""
        responses = results.responses
        if not responses:
            return {"score": 0.5, "method": "heuristic", "reasoning": "No responses to evaluate"}

        texts = [r.text for r in responses if r.text]
        if not texts:
            return {"score": 0.5, "method": "heuristic", "reasoning": "No text responses"}

        # Diversity: unique responses / total responses
        diversity = len(set(texts)) / len(texts) if texts else 0

        # Average length (too short = robotic, too long = rambling)
        avg_len = sum(len(t) for t in texts) / len(texts)
        length_score = min(1.0, avg_len / 100) if avg_len < 500 else max(0.5, 1.0 - (avg_len - 500) / 1000)

        score = (diversity * 0.5 + length_score * 0.5)

        return {
            "score": score,
            "diversity": diversity,
            "avg_response_length": avg_len,
            "method": "heuristic",
        }

    def _heuristic_score_from_log(self, log: str) -> dict[str, Any]:
        lines = log.strip().split("\n")
        return {
            "score": min(1.0, len(lines) * 0.1),
            "method": "heuristic",
            "reasoning": "LLM unavailable, scored by response count",
        }

    @staticmethod
    def _build_conversation_log(results: TestResults) -> str:
        """Format results into a readable conversation transcript."""
        lines: list[str] = []
        for r in results.responses:
            if r.text:
                lines.append(f"[{r.timestamp:.2f}s] System: {r.text}")
        for tc in results.tool_calls.calls:
            lines.append(f"[{tc.timestamp:.2f}s] Tool call: {tc.tool}({tc.args})")
        return "\n".join(sorted(lines))
