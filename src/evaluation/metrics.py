from __future__ import annotations

from dataclasses import dataclass, replace
import asyncio
import math
import time
from importlib.metadata import version as package_version
from statistics import mean
import os
import sys
import types
from typing import Any

from datasets import Dataset
from pydantic import BaseModel, Field

from core.config import Settings, normalized_provider
from core.utils import normalize_whitespace, read_json, write_json
from retrieval.index import LocalEmbeddingIndex
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.llm import build_llm
from retrieval.qa import answer_question


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5)
    correct: bool
    reasoning: str


@dataclass(frozen=True)
class EvaluationBundle:
    summary: dict[str, Any]
    answers: list[dict[str, Any]]


def _token_f1(reference: str, prediction: str) -> float:
    ref_tokens = normalize_whitespace(reference).lower().split()
    pred_tokens = normalize_whitespace(prediction).lower().split()
    if not ref_tokens or not pred_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    pred_set = set(pred_tokens)
    overlap = len(ref_set & pred_set)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_set)
    recall = overlap / len(ref_set)
    return 2 * precision * recall / (precision + recall)


def _judge_answer(settings: Settings, question: str, reference: str, prediction: str) -> tuple[JudgeVerdict, str]:
    prompt = f"""
Evaluate the model answer against the reference answer.

Question: {question}
Reference answer: {reference}
Model answer: {prediction}

Return:
- score from 1 to 5
- correct = true only when the answer is materially correct
- short reasoning
""".strip()
    try:
        llm = build_llm(settings=settings, temperature=0.0).with_structured_output(JudgeVerdict)
        return llm.invoke(prompt), "llm"
    except Exception as exc:
        if os.getenv("REQUIRE_LLM_JUDGE", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError(
                f"Required LLM judge failed for provider {normalized_provider(settings)} "
                f"and model {settings.model_name}: {type(exc).__name__}."
            ) from None
        score = 5 if _token_f1(reference, prediction) >= 0.95 else 3 if _token_f1(reference, prediction) >= 0.5 else 1
        return JudgeVerdict(
            score=score,
            correct=score >= 3,
            reasoning="Fallback heuristic judge used because the LLM evaluator was unavailable.",
        ), "heuristic_fallback"


def _run_ragas(settings: Settings, answers: list[dict[str, Any]]) -> dict[str, Any]:
    if os.getenv("RUN_RAGAS", "").lower() not in {"1", "true", "yes"}:
        return {"skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."}
    try:
        if "langchain_community.chat_models.vertexai" not in sys.modules:
            shim = types.ModuleType("langchain_community.chat_models.vertexai")
            shim.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules["langchain_community.chat_models.vertexai"] = shim
        from ragas import evaluate
        from ragas.embeddings.base import BaseRagasEmbeddings
        from ragas.llms.base import BaseRagasLLM, LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
        from ragas.run_config import RunConfig

        # The legacy Ragas metrics use permissive prompts.  Gemini can return
        # a schema-valid but empty classification list for terse answers such
        # as a date, title, or author list; Ragas then turns that into NaN.
        # Make the contract explicit at the source instead of accepting or
        # masking an invalid metric result.
        answer_relevancy.question_generation.instruction = (
            "Return exactly one question that the response directly answers. "
            "Treat a title, date, person name, identifier, or short phrase as "
            "a committal answer. Return only the required JSON object; never "
            "return Markdown, an empty question, or an empty object."
        )
        answer_relevancy.strictness = 1
        context_precision.context_precision_prompt.instruction = (
            "Decide whether this one context passage contains information that "
            "supports the given answer to the question. Return exactly one JSON "
            "object matching the schema: a non-empty reason and verdict as the "
            "integer 0 or 1. A date, title, identifier, author name, or short "
            "phrase is still an answer. Return JSON only, with no Markdown."
        )
        context_recall.context_recall_prompt.instruction = (
            "Split the reference answer into its atomic factual claims. Return "
            "a non-empty classifications array with exactly one JSON object for "
            "every claim, including a single date, title, identifier, name, or "
            "short phrase. Each object must preserve the claim in statement, "
            "include a non-empty reason, and set attributed to integer 0 or 1. "
            "Return JSON only; never return an empty array or Markdown."
        )
        faithfulness.statement_generator_prompt.instruction = (
            "Split the answer into atomic factual statements. Always return a "
            "non-empty statements array when the answer is non-empty; a date, "
            "title, identifier, author name, or short phrase is one statement. "
            "Return JSON only, with no Markdown or prose outside the schema."
        )
        faithfulness.nli_statements_prompt.instruction = (
            "For every supplied statement, return exactly one item in the "
            "statements array. Preserve the original statement verbatim, give a "
            "non-empty reason, and use verdict integer 1 only when the context "
            "directly supports it, otherwise 0. The output array must never be "
            "empty when input statements are present. Return JSON only, with no "
            "Markdown or prose outside the schema."
        )

        # Ragas' LLM metrics are mathematically undefined for an empty
        # response/reference (Faithfulness explicitly requires a response).
        # Keep those samples in the lab's deterministic metrics, but exclude
        # them from this optional Ragas pass and report the exclusion plainly.
        ragas_answers: list[dict[str, Any]] = []
        skipped_samples: list[dict[str, str]] = []
        for item in answers:
            if not normalize_whitespace(str(item.get("answer", ""))):
                skipped_samples.append({"id": str(item.get("id", "unknown")), "reason": "empty_answer"})
            elif not normalize_whitespace(str(item.get("ground_truth", ""))):
                skipped_samples.append({"id": str(item.get("id", "unknown")), "reason": "empty_ground_truth"})
            elif not item.get("retrieved_contexts"):
                skipped_samples.append({"id": str(item.get("id", "unknown")), "reason": "empty_contexts"})
            else:
                ragas_answers.append(item)
        if not ragas_answers:
            return {
                "status": "failed",
                "error": "No Ragas-eligible samples: answer, reference, and contexts are required.",
                "evaluated_sample_count": 0,
                "skipped_samples": skipped_samples,
                "dependency_version": package_version("ragas"),
            }

        dataset = Dataset.from_dict(
            {
                "question": [item["question"] for item in ragas_answers],
                "answer": [item["answer"] for item in ragas_answers],
                "ground_truth": [item["ground_truth"] for item in ragas_answers],
                "contexts": [item["retrieved_contexts"] for item in ragas_answers],
            }
        )
        class MiniLMRagasEmbeddings(BaseRagasEmbeddings):
            """Ragas 0.4-compatible adapter for the existing local MiniLM backend."""

            def __init__(self, model_name: str):
                super().__init__()
                self.delegate = MiniLMEmbeddings(model_name)

            def embed_query(self, text: str) -> list[float]:
                return self.delegate.embed_query(text)

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return self.delegate.embed_documents(texts)

            async def aembed_query(self, text: str) -> list[float]:
                return await asyncio.to_thread(self.embed_query, text)

            async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
                return await asyncio.to_thread(self.embed_documents, texts)

        class QuotaPacedRagasLLM(LangchainLLMWrapper):
            """Serialize Gemini requests below its free-tier per-minute limit."""

            def __init__(self, *args: Any, requests_per_minute: int, **kwargs: Any):
                super().__init__(*args, bypass_n=True, **kwargs)
                self._min_interval = 60.0 / max(1, requests_per_minute)
                self._last_started = 0.0
                self._request_lock = asyncio.Lock()

            async def agenerate_text(self, *args: Any, **kwargs: Any):
                # Ragas often requests n=3; Gemini returns one response and
                # accounts each prompt against the quota. One response is
                # sufficient for these metrics and prevents a hidden 3x burst.
                kwargs["n"] = 1
                async with self._request_lock:
                    delay = self._min_interval - (time.monotonic() - self._last_started)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    self._last_started = time.monotonic()
                    return await super().agenerate_text(*args, **kwargs)

        class MultiKeyRagasLLM(BaseRagasLLM):
            """Round-robin calls across comma-separated Gemini API keys."""

            def __init__(self, delegates: list[QuotaPacedRagasLLM]):
                super().__init__()
                self.delegates = delegates
                self._next_index = 0
                self._selection_lock = asyncio.Lock()

            async def _next_delegate(self) -> QuotaPacedRagasLLM:
                async with self._selection_lock:
                    delegate = self.delegates[self._next_index % len(self.delegates)]
                    self._next_index += 1
                    return delegate

            def generate_text(self, *args: Any, **kwargs: Any):
                delegate = self.delegates[self._next_index % len(self.delegates)]
                self._next_index += 1
                return delegate.generate_text(*args, **kwargs)

            async def agenerate_text(self, *args: Any, **kwargs: Any):
                return await (await self._next_delegate()).agenerate_text(*args, **kwargs)

            def is_finished(self, response: Any) -> bool:
                return self.delegates[0].is_finished(response)

            def set_run_config(self, run_config: RunConfig):
                self.run_config = run_config
                for delegate in self.delegates:
                    delegate.set_run_config(run_config)

        # Ragas 0.4.x's legacy metrics call embed_query while its abstract
        # base class requires async methods. Implement both on a native Ragas
        # adapter so no LangChain usage event receives a model object.
        api_keys = [key.strip() for key in (settings.google_api_key or "").split(",") if key.strip()]
        if not api_keys:
            api_keys = [settings.google_api_key or ""]
        requests_per_minute = int(os.getenv("RAGAS_REQUESTS_PER_MINUTE", "12"))
        ragas_llm = MultiKeyRagasLLM(
            [
                QuotaPacedRagasLLM(
                    build_llm(replace(settings, google_api_key=api_key), temperature=0.0),
                    requests_per_minute=requests_per_minute,
                )
                for api_key in api_keys
            ]
        )

        result = evaluate(
            dataset,
            metrics=[answer_relevancy, context_precision, context_recall, faithfulness],
            llm=ragas_llm,
            embeddings=MiniLMRagasEmbeddings(settings.embedding_model),
            # Keep calls below the configured per-key rate and make worker
            # count scale with an explicit comma-separated key pool.
            run_config=RunConfig(
                timeout=int(os.getenv("RAGAS_TIMEOUT_SECONDS", "180")),
                max_retries=int(os.getenv("RAGAS_MAX_RETRIES", "2")),
                max_wait=int(os.getenv("RAGAS_MAX_WAIT_SECONDS", "10")),
                max_workers=int(os.getenv("RAGAS_MAX_WORKERS", str(max(4, len(api_keys) * 4)))),
            ),
        )
        scores = getattr(result, "scores", [])
        values: dict[str, Any] = {}
        invalid_metrics: list[str] = []
        invalid_rows: list[int] = []
        if scores:
            for key in scores[0]:
                numeric = [float(row[key]) for row in scores if isinstance(row.get(key), (int, float))]
                average = sum(numeric) / len(numeric) if numeric else float("nan")
                if not math.isfinite(average):
                    invalid_metrics.append(key)
                    continue
                values[key] = average
            invalid_rows = [
                index
                for index, row in enumerate(scores)
                if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in row.values())
            ]
        metadata = {
            "evaluated_sample_count": len(ragas_answers),
            "skipped_samples": skipped_samples,
        }
        if invalid_metrics:
            values.update({
                "status": "failed",
                "error": f"Ragas returned invalid metrics: {', '.join(invalid_metrics)}",
                "invalid_row_indices": invalid_rows,
                "dependency_version": package_version("ragas"),
                **metadata,
            })
        else:
            values.update({"status": "success", "dependency_version": package_version("ragas"), **metadata})
        return values
    except Exception as exc:  # pragma: no cover
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "dependency_version": package_version("ragas"),
        }


def evaluate_pipeline(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set_path,
    metrics_output_path,
    answers_output_path,
) -> EvaluationBundle:
    test_set = read_json(test_set_path)
    answers: list[dict[str, Any]] = []

    for item in test_set:
        result = answer_question(item["question"], settings=settings, index=index)
        judge, judge_mode = _judge_answer(settings, item["question"], item["ground_truth"], result.answer)
        retrieval_hit = any(doc_id in item["ground_truth_doc_ids"] for doc_id in result.retrieved_doc_ids)
        answers.append(
            {
                "id": item["id"],
                "question_type": item["question_type"],
                "question": item["question"],
                "ground_truth": item["ground_truth"],
                "ground_truth_doc_ids": item["ground_truth_doc_ids"],
                "answer": result.answer,
                "retrieved_doc_ids": result.retrieved_doc_ids,
                "retrieved_contexts": result.retrieved_contexts,
                "retrieval_hit": retrieval_hit,
                "token_f1": _token_f1(item["ground_truth"], result.answer),
                "judge": judge.model_dump(),
                "judge_mode": judge_mode,
                "judge_provider": normalized_provider(settings),
                "judge_model": settings.model_name,
            }
        )

    llm_success_count = sum(item["judge_mode"] == "llm" for item in answers)
    fallback_count = sum(item["judge_mode"] == "heuristic_fallback" for item in answers)
    summary = {
        "samples": len(answers),
        "retrieval_hit_rate": mean(1.0 if item["retrieval_hit"] else 0.0 for item in answers) if answers else 0.0,
        "mean_token_f1": mean(item["token_f1"] for item in answers) if answers else 0.0,
        "judge_accuracy": mean(1.0 if item["judge"]["correct"] else 0.0 for item in answers) if answers else 0.0,
        "mean_judge_score": mean(item["judge"]["score"] for item in answers) if answers else 0.0,
        "judge_provider": normalized_provider(settings),
        "judge_model": settings.model_name,
        "llm_judge_success_count": llm_success_count,
        "llm_judge_fallback_count": fallback_count,
    }
    summary["ragas"] = _run_ragas(settings, answers)

    bundle = EvaluationBundle(summary=summary, answers=answers)
    write_json(metrics_output_path, summary)
    write_json(answers_output_path, answers)
    return bundle
