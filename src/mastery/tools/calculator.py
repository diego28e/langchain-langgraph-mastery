"""A safe calculator: arithmetic only, no ``eval``.

Lesson 02.01 explains why: the LangChain docs' calculator example uses
``eval(expression)``, which runs *any* Python the model (or a prompt injection
hidden in a document) writes, e.g. ``__import__('os').remove(...)``. Tools run
with your permissions, so a tool must only do what its name promises.

``safe_eval`` parses the text into a syntax tree (``ast``) and evaluates only
numbers, parentheses, and the operators + - * / // % ** (unary + and - too).
Everything else (names, calls, attributes, strings) is rejected.
"""

from __future__ import annotations

import ast
import math
import operator

from langchain_core.tools import ToolException, tool

__all__ = ["CalculatorError", "calculator", "safe_eval"]

MAX_LENGTH = 200          # Characters. Long inputs are a sign something is off.
MAX_EXPONENT = 100        # 10 ** 100000 would freeze the kernel.
MAX_MAGNITUDE = 1e15      # Keep results human-scale (money, counts, dates).

_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class CalculatorError(ToolException):
    """The expression is not plain arithmetic, or is out of safe bounds.

    Subclasses ``ToolException``: a tool with ``handle_tool_error=True`` turns it
    into an error ``ToolMessage`` the model can read and fix.
    """


def safe_eval(expression: str) -> float | int:
    """Evaluate plain arithmetic safely.

    Args:
        expression: e.g. ``"(1200 + 300) * 0.19"``. ``^`` is accepted as power.

    Returns:
        An ``int`` when the result is whole and both sides were ints, else a ``float``.

    Raises:
        CalculatorError: Empty, too long, not arithmetic, division by zero, or too large.
    """
    text = (expression or "").strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    if not text:
        raise CalculatorError("Empty expression. Send something like '12 * (3 + 4)'.")
    if len(text) > MAX_LENGTH:
        raise CalculatorError(f"Expression longer than {MAX_LENGTH} characters.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Not a valid arithmetic expression: {expression!r}") from exc
    result = _eval(tree.body)
    if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
        raise CalculatorError("Result is not a finite number.")
    return result


def _eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalculatorError(f"Exponent larger than {MAX_EXPONENT}.")
        try:
            value = _BINARY[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise CalculatorError("Division by zero.") from exc
        if isinstance(value, complex) or abs(value) > MAX_MAGNITUDE:
            raise CalculatorError(f"Result outside the safe range (|x| <= {MAX_MAGNITUDE:g}).")
        return value
    raise CalculatorError(
        f"Only numbers and + - * / // % ** ( ) are allowed; found {type(node).__name__}."
    )


@tool(parse_docstring=True)
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly. Use it for ANY calculation instead of doing math yourself.

    Args:
        expression: Plain arithmetic with numbers, + - * / // % ** and parentheses, e.g. "(1250.5 + 349.5) * 0.19". No variables, units or words.
    """
    value = safe_eval(expression)
    if isinstance(value, float):
        value = round(value, 10)  # Hide float noise like 0.30000000000000004.
    return str(value)


calculator.handle_tool_error = True   # CalculatorError -> error ToolMessage, the model can retry.
