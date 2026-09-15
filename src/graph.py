import os
import re
import json
import tempfile
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.parser_agent import parser_agent
from src.modernizer_agent import modernizer_agent, get_llm
from src.test_generator_agent import test_generator_agent
from src.sandbox import CobolSandbox

def execute_python_loan(python_code: str, test_case: dict) -> dict:
    """Dynamically executes the generated Python code in an isolated scope."""
    exec_scope = {}
    exec(python_code, exec_scope)
    evaluate_loan = exec_scope.get("evaluate_loan")
    if not evaluate_loan:
        raise ValueError("Generated Python code does not define 'evaluate_loan'")

    return evaluate_loan(
        cust_id=test_case["cust_id"],
        credit_score=test_case["credit_score"],
        annual_income=test_case["annual_income"],
        existing_monthly_debt=test_case["existing_monthly_debt"],
        requested_loan_amt=test_case["requested_loan_amt"],
        loan_term_months=test_case["loan_term_months"],
        employment_status=test_case["employment_status"],
        prior_bankruptcy=test_case["prior_bankruptcy"]
    )

def parity_verifier_node(state: AgentState) -> dict:
    """Executes COBOL via CobolSandbox and Python side-by-side on all test vectors."""
    test_cases = state["generated_test_cases"]
    python_code = state["python_code"]
    cobol_source = state["cobol_source"]

    # Write COBOL source to a temporary file for CobolSandbox
    temp_dir = tempfile.mkdtemp()
    temp_cbl = os.path.join(temp_dir, "temp_engine.cbl")
    with open(temp_cbl, "w", encoding="utf-8") as f:
        f.write(cobol_source)

    sandbox = CobolSandbox(temp_cbl)
    compiled, compile_msg = sandbox.compile()
    if not compiled:
        raise RuntimeError(f"Sandbox compilation failed: {compile_msg}")

    discrepancies = []
    print(f"\n--- Running Differential Parity Suite ({len(test_cases)} tests) ---")

    for tc in test_cases:
        test_id = tc["test_id"]
        inputs = [
            str(tc["cust_id"]),
            str(tc["credit_score"]),
            f"{tc['annual_income']:.2f}",
            f"{tc['existing_monthly_debt']:.2f}",
            f"{tc['requested_loan_amt']:.2f}",
            f"{tc['loan_term_months']:03d}",
            str(tc["employment_status"]),
            str(tc["prior_bankruptcy"])
        ]

        ok, cobol_res = sandbox.execute(inputs)
        if not ok:
            print(f"FAIL: {test_id} - COBOL runtime error: {cobol_res}")
            discrepancies.append({"test_id": test_id, "error": cobol_res})
            continue

        try:
            python_res = execute_python_loan(python_code, tc)
        except Exception as e:
            python_res = {"ERROR": str(e)}

        # Compare outputs
        mismatches = {}
        for key, c_val in cobol_res.items():
            normalized_key = key.replace("-", "_").upper()
            py_val = str(python_res.get(normalized_key, python_res.get(key, ""))).strip()
            if str(c_val).strip() != py_val:
                mismatches[key] = {"cobol": str(c_val).strip(), "python": py_val}

        if mismatches:
            discrepancies.append({
                "test_id": test_id,
                "description": tc.get("description", ""),
                "mismatches": mismatches
            })
            print(f"FAIL: {test_id} - Mismatch in keys: {list(mismatches.keys())}")
        else:
            print(f"PASS: {test_id} - Exact parity achieved.")

    parity_passed = len(discrepancies) == 0
    return {
        "parity_passed": parity_passed,
        "discrepancy_log": discrepancies,
        "iteration_count": state["iteration_count"] + 1
    }

def reflection_agent_node(state: AgentState) -> dict:
    """Self-healing node: rewrites the Python code when parity discrepancies are found."""
    print(f"\n[Reflection Loop] Self-healing initiated (Iteration {state['iteration_count']}/3)...")
    llm = get_llm()

    system_prompt = (
        "You are an expert Python modernization debugger. The generated Python code has\n"
        "arithmetic or formatting discrepancies when compared against native COBOL executions.\n"
        "Review the discrepancies and output the corrected full Python code inside ```python ... ```."
    )

    user_prompt = (
        f"Original Python Code:\n```python\n{state['python_code']}\n```\n\n"
        f"Discrepancies Observed:\n```json\n{json.dumps(state['discrepancy_log'], indent=2)}\n```\n\n"
        "Provide the corrected `evaluate_loan` implementation fixing all discrepancies."
    )

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    match = re.search(r"```python\s*(.*?)\s*```", response.content, re.DOTALL)
    repaired_code = match.group(1) if match else response.content.strip()

    return {"python_code": repaired_code}

def should_continue(state: AgentState) -> str:
    """Controls the cyclic graph flow."""
    if state["parity_passed"]:
        return "end"
    if state["iteration_count"] >= 3:
        print("\n[Warning] Maximum iterations reached. Exiting loop.")
        return "end"
    return "reflect"

def build_modernization_graph():
    """Compiles the LangGraph state machine."""
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", parser_agent)
    workflow.add_node("modernizer", modernizer_agent)
    workflow.add_node("test_generator", test_generator_agent)
    workflow.add_node("verifier", parity_verifier_node)
    workflow.add_node("reflector", reflection_agent_node)

    workflow.set_entry_point("parser")

    workflow.add_edge("parser", "modernizer")
    workflow.add_edge("modernizer", "test_generator")
    workflow.add_edge("test_generator", "verifier")

    workflow.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "end": END,
            "reflect": "reflector"
        }
    )
    workflow.add_edge("reflector", "verifier")

    return workflow.compile()

if __name__ == "__main__":
    cobol_path = "tests/synthetic_cobol/loan_risk_engine.cbl"
    with open(cobol_path, "r", encoding="utf-8") as f:
        source = f.read()

    app = build_modernization_graph()

    initial_input: AgentState = {
        "cobol_source": source,
        "semantic_ast": None,
        "python_code": None,
        "generated_test_cases": None,
        "parity_passed": False,
        "discrepancy_log": None,
        "iteration_count": 0
    }

    print("Executing Autonomous Legacy Modernization Engine...\n")
    final_output = app.invoke(initial_input)

    print("\n" + "=" * 60)
    print(f"PARITY VERIFIED: {final_output['parity_passed']}")
    print(f"TOTAL ITERATIONS: {final_output['iteration_count']}")
    print("=" * 60)