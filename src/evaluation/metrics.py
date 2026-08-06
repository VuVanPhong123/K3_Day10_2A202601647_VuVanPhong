from __future__ import annotations

from dataclasses import dataclass
import asyncio
import math
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
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

        dataset = Dataset.from_dict(
            {
                "question": [item["question"] for item in answers],
                "answer": [item["answer"] for item in answers],
                "ground_truth": [item["ground_truth"] for item in answers],
                "contexts": [item["retrieved_contexts"] for item in answers],
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

        # Ragas 0.4.x's legacy metrics call embed_query while its abstract
        # base class requires async methods. Implement both on a native Ragas
        # adapter so no LangChain usage event receives a model object.
        result = evaluate(
            dataset,
            metrics=[answer_relevancy, context_precision, context_recall, faithfulness],
            llm=build_llm(settings=settings, temperature=0.0),
            embeddings=MiniLMRagasEmbeddings(settings.embedding_model),
        )
        scores = getattr(result, "scores", [])
        values: dict[str, Any] = {}
        invalid_metrics: list[str] = []
        if scores:
            for key in scores[0]:
                numeric = [float(row[key]) for row in scores if isinstance(row.get(key), (int, float))]
                average = sum(numeric) / len(numeric) if numeric else float("nan")
                if not math.isfinite(average):
                    invalid_metrics.append(key)
                    continue
                values[key] = average
        if invalid_metrics:
            values.update({
                "status": "failed",
                "error": f"Ragas returned invalid metrics: {', '.join(invalid_metrics)}",
                "dependency_version": package_version("ragas"),
            })
        else:
            values.update({"status": "success", "dependency_version": package_version("ragas")})
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
