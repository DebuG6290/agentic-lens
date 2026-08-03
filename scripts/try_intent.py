"""
Manual smoke test for the clarification loop. Needs Ollama running locally.
Run from the repo root: python scripts/try_intent.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from intent_parser import parse_intent

result = parse_intent("Trump affects my hospital business")
print("STATUS:", result["status"])

if result["status"] == "error":
    print("ERROR:", result["message"])
    sys.exit(1)

print("TOKENS:", result["tokens"])

if result["status"] == "needs_clarification":
    print("\nQUESTIONS FROM MODEL:\n", result["questions"])

    user_answer = input("\nYour answer: ")
    result2 = parse_intent(user_answer, conversation_history=result["history"])

    print("\nSTATUS:", result2["status"])

    if result2["status"] == "error":
        print("ERROR:", result2["message"])
        sys.exit(1)

    print("TOKENS:", result2["tokens"])

    if result2["status"] == "complete":
        print("\nMECHANISM OBJECT:\n", result2["mechanism_object"])
    else:
        print("\nMORE QUESTIONS:\n", result2["questions"])
else:
    print("\nMECHANISM OBJECT:\n", result["mechanism_object"])
