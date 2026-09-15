import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
from langchain_anthropic import ChatAnthropic
from src.state import AgentState

load_dotenv()

class TestCase(BaseModel):
    test_id: str = Field(description="Unique identifier for the test case")
    description: str = Field(description="Purpose of the test case, e.g., 'Boundary: Credit Score 580'")
    cust_id: str
    credit_score: int
    annual_income: float
    existing_monthly_debt: float
    requested_loan_amt: float
    loan_term_months: int
    employment_status: str
    prior_bankruptcy: str

class TestSuite(BaseModel):
    test_cases: List[TestCase] = Field(description="A comprehensive list of targeted test cases")

def get_llm():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in the .env file.")
    return ChatAnthropic(
        model_name="claude-haiku-4-5-20251001",
        temperature=0.0,
        anthropic_api_key=api_key
    )

def test_generator_agent(state: AgentState) -> dict:
    """
    Agent 3: Generates edge cases, boundary conditions, and typical test vectors.
    """
    semantic_ast = state.get("semantic_ast")
    if not semantic_ast:
        raise ValueError("No SemanticAST found in state for Test Generator Agent.")

    llm = get_llm()
    structured_llm = llm.with_structured_output(TestSuite)

    system_prompt = (
        "You are an expert QA and Differential Testing Engineer for financial software.\n"
        "Given the Semantic AST of a legacy loan engine, generate 5-6 highly targeted test cases.\n\n"
        "Required test scenarios:\n"
        "1. Golden Path: Prime applicant (Credit > 780, low DTI, Full-time) expecting Grade A.\n"
        "2. Bankruptcy Filter: Prior bankruptcy = 'Y' (should reject immediately).\n"
        "3. Low Credit Boundary: Credit score = 579 (1 point below 580 minimum).\n"
        "4. High DTI Rejection: DTI exceeds 45.00%.\n"
        "5. Long-term Surcharge: Loan term > 60 months (verifies the +0.75% rate adjustment).\n"
        "Ensure realistic numeric values matching the schema types."
    )

    user_prompt = f"Semantic AST:\n```json\n{json.dumps(semantic_ast, indent=2)}\n```"

    result: TestSuite = structured_llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    test_case_dicts = [tc.model_dump() for tc in result.test_cases]
    return {"generated_test_cases": test_case_dicts}

if __name__ == "__main__":
    from src.parser_agent import parser_agent

    cobol_path = "tests/synthetic_cobol/loan_risk_engine.cbl"
    with open(cobol_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    state: AgentState = {
        "cobol_source": source_text,
        "semantic_ast": None,
        "python_code": None,
        "generated_test_cases": None,
        "parity_passed": False,
        "discrepancy_log": None,
        "iteration_count": 0
    }

    print("Step 1: Parsing COBOL...")
    state.update(parser_agent(state))

    print("Step 2: Generating Boundary Test Cases...")
    test_result = test_generator_agent(state)
    state.update(test_result)

    print("\nGenerated Test Vectors:")
    print("=" * 60)
    print(json.dumps(state["generated_test_cases"], indent=2))
    print("=" * 60)