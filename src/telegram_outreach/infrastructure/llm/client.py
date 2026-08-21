"""Ollama httpx client implementing LLMClientPort."""
from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from ...config.logging import get_logger
from ...config.settings import Settings
from ...domain.entities import Lead, Vacancy
from ...domain.exceptions import LLMContractError
from ...ports.llm import DraftMessage, ReplyAnalysis, ScoreResult, VacancyParse
from . import prompts
from .parser import extract_json

_log = get_logger(__name__)


class OllamaClient:
    """Async client for Ollama's /api/chat endpoint.

    The class implements the LLMClientPort. It does NOT depend on domain
    entities for I/O (only as inputs to methods).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=httpx.Timeout(self._settings.ollama_timeout_seconds),
            )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OllamaClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    # --- Public API ---------------------------------------------------------
    async def classify_vacancy(self, text: str) -> VacancyParse:
        raw = await self._chat_json(
            prompts.VACANCY_SYSTEM,
            prompts.VACANCY_USER_TEMPLATE.format(text=text[:6000]),
        )
        return VacancyParse(
            is_vacancy=bool(raw.get("is_vacancy", False)),
            kind=str(raw.get("kind", "other")),
            title=str(raw.get("title", ""))[:120],
            description=str(raw.get("description", ""))[:1000],
            requirements=[str(x) for x in (raw.get("requirements") or [])][:20],
            has_budget=bool(raw.get("has_budget", False)),
            contact_username=(str(raw["contact_username"]).lstrip("@").lower()
                              if raw.get("contact_username") else None),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
            raw=raw,
        )

    async def score_relevance(self, vacancy: Vacancy) -> ScoreResult:
        requirements = "\n".join(f"- {r}" for r in vacancy.requirements) or "—"
        raw = await self._chat_json(
            prompts.SCORE_SYSTEM,
            prompts.SCORE_USER_TEMPLATE.format(
                title=vacancy.title or "(no title)",
                description=vacancy.description or "(no description)",
                requirements=requirements,
            ),
        )
        score = float(raw.get("score", 0.0) or 0.0)
        return ScoreResult(
            score=max(0.0, min(1.0, score)),
            reason=str(raw.get("reason", ""))[:500],
        )

    async def generate_message(self, lead: Lead) -> DraftMessage:
        v = lead.vacancy
        requirements = "\n".join(f"- {r}" for r in v.requirements) or "—"
        raw = await self._chat_json(
            prompts.GENERATE_SYSTEM,
            prompts.GENERATE_USER_TEMPLATE.format(
                title=v.title or "(no title)",
                description=v.description or "(no description)",
                requirements=requirements,
                detected_need=v.metadata.get("detected_need", "(unspecified)"),
                score=f"{lead.score.value:.2f}",
            ),
        )
        return DraftMessage(
            detected_need=str(raw.get("detected_need", ""))[:300],
            proposed_solution=str(raw.get("proposed_solution", ""))[:300],
            message=str(raw.get("message", "")).strip()[:1000],
            raw=raw,
        )

    async def analyze_reply(
        self, message: str, conversation_context: str
    ) -> ReplyAnalysis:
        raw = await self._chat_json(
            prompts.REPLY_SYSTEM,
            prompts.REPLY_USER_TEMPLATE.format(
                outreach=conversation_context[:2000],
                reply=message[:2000],
            ),
        )
        intent = str(raw.get("intent", "other")).lower()
        if intent not in {"interested", "not_interested", "question", "opt_out", "other"}:
            intent = "other"
        return ReplyAnalysis(
            intent=intent,
            summary=str(raw.get("summary", ""))[:300],
            requires_followup=bool(raw.get("requires_followup", False)),
        )

    # --- Internals ----------------------------------------------------------
    async def _chat_json(self, system: str, user: str, *, attempts: int = 3) -> dict[str, Any]:
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                resp = await self._post_chat(system, user)
                text = self._extract_text(resp)
                return extract_json(text)
            except (LLMContractError, httpx.HTTPError) as e:
                last_err = e
                backoff = min(2 ** i, 8) + random.uniform(0, 1)
                _log.warning("llm.retry", attempt=i + 1, error=str(e), sleep=backoff)
                await asyncio.sleep(backoff)
        raise LLMContractError(f"LLM failed after {attempts} attempts: {last_err}")

    async def _post_chat(self, system: str, user: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OllamaClient not started")
        body = {
            "model": self._settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.2},
        }
        r = await self._client.post("/api/chat", json=body)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _extract_text(resp: dict[str, Any]) -> str:
        if "message" in resp and isinstance(resp["message"], dict):
            return resp["message"].get("content", "")
        if "response" in resp:
            return resp["response"]
        raise LLMContractError(f"unexpected Ollama response shape: {list(resp.keys())}")
