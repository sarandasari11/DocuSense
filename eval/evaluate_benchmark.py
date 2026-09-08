import os
import sys
import json
import time
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database.db import init_db, engine
from app.models.document import Document
from app.services.ingestion import ingestion_service
from app.services.retrieval import hybrid_retriever
from app.services.rag import rag_engine
from datetime import date
from sqlmodel import Session, select

def run_benchmark():
    init_db()
    
    # Ensure sample documents are indexed for evaluation
    path_2024 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "sample_data", "HR_Policy_2024.txt"))
    path_2026 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "sample_data", "HR_Policy_2026.txt"))
    
    with Session(engine) as session:
        existing_docs = session.exec(select(Document)).all()
        if not existing_docs:
            doc_24 = Document(
                filename="HR_Policy_2024.txt",
                file_type="txt",
                file_path=path_2024,
                title="HR Policy 2024",
                version="2024.1",
                effective_from=date(2024, 1, 1),
                status="pending"
            )
            session.add(doc_24)
            session.commit()
            session.refresh(doc_24)
            ingestion_service.process_document(doc_24.id)

            doc_26 = Document(
                filename="HR_Policy_2026.txt",
                file_type="txt",
                file_path=path_2026,
                title="HR Policy 2026",
                version="2026.1",
                effective_from=date(2026, 1, 1),
                status="pending"
            )
            session.add(doc_26)
            session.commit()
            session.refresh(doc_26)
            ingestion_service.process_document(doc_26.id)

    dataset_path = os.path.join(os.path.dirname(__file__), "dataset", "ground_truth_qa.json")
    with open(dataset_path, "r") as f:
        qa_pairs = json.load(f)

    def expected_documents(item):
        if item["relevant_doc"] == "Both":
            return {"HR Policy 2024", "HR Policy 2026"}
        return {item["relevant_doc"]}

    def evaluate_mode(mode):
        total_precision = 0.0
        total_recall = 0.0
        total_latency = 0.0
        reciprocal_rank = 0.0
        for item in qa_pairs:
            started = time.time()
            if mode == "hybrid":
                candidates = hybrid_retriever.hybrid_search(
                    item["question"], limit=5, year=item.get("target_year")
                )
                names = [candidate.document_name for candidate in candidates]
            elif mode == "dense":
                results = hybrid_retriever.search_dense(
                    item["question"], limit=5, year=item.get("target_year")
                )
                names = [result["document_name"] for result in results]
            else:
                results = hybrid_retriever.search_sparse_bm25(
                    item["question"], limit=5, year=item.get("target_year")
                )
                names = [result["document_name"] for result in results]

            expected = expected_documents(item)
            hits = [name for name in names if name in expected]
            total_precision += len(hits) / len(names) if names else 0.0
            total_recall += len(set(hits)) / len(expected)
            for rank, name in enumerate(names, 1):
                if name in expected:
                    reciprocal_rank += 1 / rank
                    break
            total_latency += (time.time() - started) * 1000

        count = len(qa_pairs)
        return {
            "precision_at_5": round(total_precision / count, 3),
            "recall_at_5": round(total_recall / count, 3),
            "mrr": round(reciprocal_rank / count, 3),
            "avg_latency_ms": round(total_latency / count, 2),
            "total": count,
        }

    print("==================================================================")
    print("      DOCUSENSE EXPERIMENTAL BENCHMARKING (RESEARCH EVALUATION)    ")
    print("==================================================================")

    results = {mode: evaluate_mode(mode) for mode in ("dense", "bm25", "hybrid")}

    print("\n--- Comparative Experimental Results ---")
    print(f"{'Retriever':<16} | {'Precision@5':<14} | {'Recall@5':<12} | {'MRR':<8} | {'Avg Latency (ms)':<16}")
    print("-" * 78)
    
    for name, stats in results.items():
        print(f"{name:<16} | {stats['precision_at_5']:<14.3f} | {stats['recall_at_5']:<12.3f} | {stats['mrr']:<8.3f} | {stats['avg_latency_ms']:<16}")

    print("\nJSON metrics:")
    print(json.dumps(results, indent=2))

    print("==================================================================")

if __name__ == "__main__":
    run_benchmark()
