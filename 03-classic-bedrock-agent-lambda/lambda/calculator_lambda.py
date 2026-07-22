"""
Lambda function backing the Bedrock Agent's "calculate" action.

Simple version: regex-checks the expression only contains digits/operators/parens (blocks
letters, function calls, etc.) before calling eval(). Not as rigorous as a full AST-based
evaluator, but much shorter and easier to read for a learning example.

Bedrock invokes this with an event shaped like:
{
  "messageVersion": "1.0",
  "actionGroup": "CalculatorActions",
  "function": "calculate",
  "parameters": [{"name": "expression", "type": "string", "value": "25 * 4"}],
  ...
}

And expects a response shaped like:
{
  "messageVersion": "1.0",
  "response": {
    "actionGroup": "...",
    "function": "...",
    "functionResponse": {"responseBody": {"TEXT": {"body": "<result as string>"}}}
  }
}
"""
import re

ALLOWED_CHARS = re.compile(r"^[0-9+\-*/(). ]+$")


def calculate(expression: str):
    if not ALLOWED_CHARS.match(expression):
        raise ValueError("Only numbers and + - * / ( ) are allowed")
    return eval(expression, {"__builtins__": {}}, {})


def lambda_handler(event, context):
    action_group = event.get("actionGroup", "")
    function = event.get("function", "")
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}
    expression = params.get("expression", "")

    try:
        body = str(calculate(expression))
    except Exception as exc:
        body = f"Could not evaluate '{expression}': {exc}"

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function,
            "functionResponse": {
                "responseBody": {"TEXT": {"body": body}}
            },
        },
    }
