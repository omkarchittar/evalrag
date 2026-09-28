"""Safe local tools; no eval(), arbitrary attributes, function calls or imports."""

import ast
import math
import operator

OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calculate(expression: str) -> float:
    if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
        raise ValueError("Expression must contain 1–256 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Invalid arithmetic expression") from exc
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("Expression is too complex")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = node.value
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            result = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1_000_000):
                raise ValueError("Exponent exceeds the calculation limit")
            result = OPERATIONS[type(node.op)](left, right)
        else:
            raise ValueError("Only numeric arithmetic is permitted")
        if isinstance(result, complex) or abs(result) > 1e15 or not math.isfinite(result):
            raise ValueError("Result exceeds the calculation limit")
        return result

    try:
        return visit(tree.body)
    except (OverflowError, ZeroDivisionError, RecursionError) as exc:
        raise ValueError("Arithmetic operation is outside allowed bounds") from exc


def validate_citations(citations: list[dict], sources: dict[str, str]) -> list[dict]:
    """Verify source existence and verbatim quotes, NOT semantic entailment.

    Whitespace is normalized because PDFs and layout extraction introduce linebreaks.
    Claims and quotes remain separate so an evaluator can score actual claim support.
    """
    result = []
    for citation in citations:
        source = sources.get(citation.get("chunk_id"))
        quote = citation.get("quote")
        if source is None:
            reason = "unknown_source"
        elif not isinstance(quote, str) or not quote.strip():
            reason = "empty_quote"
        elif " ".join(quote.split()) not in " ".join(source.split()):
            reason = "quote_not_found"
        else:
            reason = None
        result.append({**citation, "valid": reason is None, "reason": reason})
    return result
