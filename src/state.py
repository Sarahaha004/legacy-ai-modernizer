from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ASTNode(BaseModel):
    """Represents one atomic piece extracted from the COBOL code."""
    node_type: str = Field(description="Type: 'variable', 'rule', or 'formula'")
    name: str = Field(description="Identifier or paragraph name")
    details: Dict[str, Any] = Field(description="Properties, data types, conditions")

class SemanticAST(BaseModel):
    """The structured summary form produced by the Parser Agent."""
    program_name: str = Field(description="Name from IDENTIFICATION DIVISION")
    variables: List[Dict[str, Any]] = Field(description="Variables, PIC clauses, defaults")
    rules: List[Dict[str, Any]] = Field(description="Validation rules and hard filters")
    formulas: List[Dict[str, Any]] = Field(description="Math calculations and logic")

class AgentState(TypedDict):
    """The shared memory folder passed between all agents in LangGraph."""
    cobol_source: str
    semantic_ast: Optional[Dict[str, Any]]
    python_code: Optional[str]
    generated_test_cases: Optional[List[Dict[str, Any]]]
    parity_passed: bool
    discrepancy_log: Optional[str]
    iteration_count: int
    