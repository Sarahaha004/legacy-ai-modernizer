import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from src.state import AgentState, SemanticAST

# Load API keys from the .env file
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

def parser_agent(state: AgentState) -> dict:
    """
    Agent 1: Analyzes raw COBOL code and extracts a structured SemanticAST.
    """
    cobol_code = state.get("cobol_source", "")
    if not cobol_code:
        raise ValueError("No COBOL source code provided in state.")

    llm = get_llm()
    
    # Force the LLM to output data matching our SemanticAST Pydantic schema
    structured_llm = llm.with_structured_output(SemanticAST)

    system_prompt = (
        "You are an expert COBOL Mainframe Systems Analyst and Reverse Engineer.\n"
        "Your task is to analyze the provided COBOL source code and extract an accurate "
        "Semantic Abstract Syntax Tree (AST).\n\n"
        "Instructions:\n"
        "1. Extract the program name from IDENTIFICATION DIVISION.\n"
        "2. Parse all variables from WORKING-STORAGE SECTION, noting their COBOL PIC clause "
        "and their target Python data type (e.g., PIC 9(3) -> int, PIC 9(7)V99 -> float, PIC X -> str).\n"
        "3. Identify all validation rules, condition checks (88-levels, IF statements), and hard filters.\n"
        "4. Extract all business formulas, arithmetic computations (COMPUTE, ADD), and risk matrices.\n"
    )

    user_prompt = f"COBOL Source Code:\n```cobol\n{cobol_code}\n```"

    # Invoke the model with structured output guarantee
    extracted_ast: SemanticAST = structured_llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    # Return only the updated field to merge into LangGraph AgentState
    return {"semantic_ast": extracted_ast.model_dump()}

if __name__ == "__main__":
    cobol_path = "tests/synthetic_cobol/loan_risk_engine.cbl"
    with open(cobol_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    initial_state: AgentState = {
        "cobol_source": source_text,
        "semantic_ast": None,
        "python_code": None,
        "generated_test_cases": None,
        "parity_passed": False,
        "discrepancy_log": None,
        "iteration_count": 0
    }

    print("Running Legacy Parser Agent...")
    result = parser_agent(initial_state)
    import json
    print("\nExtracted Semantic AST:")
    print(json.dumps(result["semantic_ast"], indent=2))
    