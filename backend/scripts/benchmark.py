import asyncio
import json
import os
import sys
from pathlib import Path
import time

# Add backend to path so imports work identically to uvicorn
sys.path.append(str(Path(__file__).parent.parent))

from agents.jd_parser import parse_job_description
from utils.llm import llm_generate_json
from pydantic import BaseModel, Field

class LLMJudgeScore(BaseModel):
    score: int = Field(description="Score from 1 to 5, where 5 is perfect extraction and 1 is terrible.")
    reasoning: str = Field(description="1-2 sentences explaining the score based on the ground truth.")

def calculate_recall(expected: list, actual: list) -> float:
    if not expected:
        return 1.0 if not actual else 0.0
    
    expected_lower = [e.lower() for e in expected]
    actual_lower = [a.lower() for a in actual]
    
    hits = 0
    for e in expected_lower:
        # Check if expected word is anywhere in the actual list
        if any(e in a or a in e for a in actual_lower):
            hits += 1
            
    return hits / len(expected)

async def evaluate_subjective_quality(test_case: dict, actual_output: dict) -> LLMJudgeScore:
    """Uses LLM as a judge to grade the output."""
    prompt = f"""
    You are an expert AI evaluator. Grade the extraction quality of the system.
    
    GROUND TRUTH EXPECTED DATA:
    {json.dumps(test_case['expected'], indent=2)}
    
    ACTUAL AI OUTPUT:
    {json.dumps(actual_output, indent=2)}
    
    Grade how well the ACTUAL OUTPUT matches the GROUND TRUTH on a scale from 1-5.
    Penalize heavily for hallucinations (making up data not in truth) or missing critical fields.
    """
    
    try:
        # Use gemini to grade itself
        score_data = await llm_generate_json(prompt, max_tokens=150, temperature=0.0, response_schema=LLMJudgeScore)
        return LLMJudgeScore(**score_data)
    except Exception as e:
        print(f"Failed to judge: {e}")
        return LLMJudgeScore(score=0, reasoning="Judge failed")

async def run_benchmarks():
    print("🚀 Starting HireScope Evaluation Framework...")
    data_path = Path(__file__).parent.parent / "data" / "eval_dataset.json"
    
    with open(data_path, "r") as f:
        datasets = json.load(f)
        
    total_score = 0
    max_score = 0
    results = []
    
    for case in datasets:
        print(f"\nEvaluating Test Case: {case['name']}...")
        start_time = time.time()
        
        try:
            # 1. Run the target pipeline
            actual = await parse_job_description(case['raw_html'], provider="gemini")
            actual_dict = actual.model_dump() if hasattr(actual, "model_dump") else actual
            
            # 2. Score Schema Compliance (if it didn't throw an error, it's 100%)
            schema_score = 100
            
            # 3. Score Recall (Skills)
            expected_skills = case['expected'].get('required_skills', [])
            actual_skills = actual_dict.get('required_skills', [])
            recall = calculate_recall(expected_skills, actual_skills)
            
            # 4. LLM as a Judge
            judge_evaluation = await evaluate_subjective_quality(case, actual_dict)
            
            elapsed = time.time() - start_time
            
            print(f"✅ Pass in {elapsed:.2f}s")
            print(f"   Schema Compliance: {schema_score}%")
            print(f"   Skills Recall:     {recall * 100:.1f}% ({len(actual_skills)} extracted vs {len(expected_skills)} expected)")
            print(f"   Judge Score:       {judge_evaluation.score}/5 - {judge_evaluation.reasoning}")
            
            total_score += (recall * 100) + (judge_evaluation.score * 20)
            max_score += 200
            
            results.append({
                "id": case["id"],
                "status": "success",
                "recall": recall,
                "judge_score": judge_evaluation.score
            })
            
        except Exception as e:
            print(f"❌ Failed: {type(e).__name__} - {str(e)}")
            results.append({
                "id": case["id"],
                "status": "failed",
                "error": str(e)
            })
            
    print("\n" + "="*50)
    print("📊 BENCHMARK AGGREGATE RESULTS")
    print("="*50)
    if max_score > 0:
        final_score = (total_score / max_score) * 100
        print(f"Overall Pipeline Score: {final_score:.1f}%")
    else:
        print("No successful runs to score.")
    
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"Pass Rate: {success_count}/{len(datasets)} test cases completed.")

if __name__ == "__main__":
    asyncio.run(run_benchmarks())
