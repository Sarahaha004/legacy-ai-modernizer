import os
import re
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from src.state import AgentState

load_dotenv()

def get_llm():
    """Initializes and returns the language model instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in the .env file.")
    return ChatAnthropic(
        model_name="claude-haiku-4-5-20251001",
        temperature=0.0,
        anthropic_api_key=api_key
    )

def modernizer_agent(state: AgentState) -> dict:
    """
    Agent 2: Transforms the SemanticAST into idiomatic, deterministic Python code.
    """
    semantic_ast = state.get("semantic_ast")
    if not semantic_ast:
        raise ValueError("No SemanticAST found in state for Modernizer Agent.")

    llm = get_llm()

    system_prompt = (
        "You are an expert Python Software Architect specializing in legacy modernization.\n"
        "Your task is to convert an extracted COBOL Semantic AST into idiomatic, deterministic Python 3.11+ code.\n\n"
        "Requirements:\n"
        "1. Write a standalone Python module with a main function named `evaluate_loan`.\n"
        "2. The function `evaluate_loan` must accept keyword arguments matching the input fields:\n"
        "   - cust_id (str)\n"
        "   - credit_score (int)\n"
        "   - annual_income (float)\n"
        "   - existing_monthly_debt (float)\n"
        "   - requested_loan_amt (float)\n"
        "   - loan_term_months (int)\n"
        "   - employment_status (str)\n"
        "   - prior_bankruptcy (str)\n"
        "3. Emulate all validation rules, risk scoring, interest rates, origination fees, and EMI calculations strictly.\n"
        "4. Return a Python dictionary with keys and string-formatted values matching the legacy COBOL DISPLAY format:\n"
        "   If approved:\n"
        "     STATUS: 'Y', CUSTOMER_ID: str, RISK_GRADE: str, RISK_SCORE: f'{score:03d}',\n"
        "     DTI_RATIO: f'{dti:06.2f}', INTEREST_RATE: f'{rate:05.2f}', ORIGINATION_FEE: f'{fee:08.2f}',\n"
        "     TOTAL_INTEREST: f'{interest:010.2f}', TOTAL_REPAYMENT: f'{repayment:011.2f}', MONTHLY_EMI: f'{emi:09.2f}'\n"
        "   If rejected:\n"
        "     STATUS: 'N', REASON: str\n"
        "5. Output ONLY raw executable Python code inside a markdown python block: ```python ... ``` without conversational fluff."
    )

    import json
    user_prompt = f"Semantic AST:\n```json\n{json.dumps(semantic_ast, indent=2)}\n```"

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    code_text = response.content

    # Extract code from Markdown blocks if present
    match = re.search(r"```python\s*(.*?)\s*```", code_text, re.DOTALL)
    if match:
        extracted_python = match.group(1)
    else:
        extracted_python = code_text.strip()

    return {"python_code": extracted_python}

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

    print("Step 1: Running Parser Agent...")
    state.update(parser_agent(state))

    print("Step 2: Running Modernizer Agent (Generating Python Code)...")
    result = modernizer_agent(state)
    state.update(result)

    print("\nGenerated Modern Python Code:")
    print("=" * 60)
    print(state["python_code"])
    print("=" * 60)