"""
test_consultant_agent.py
────────────────────────
Scenario tests for the consultant agent.
Run from backend/:
    python test_consultant_agent.py

Tests are standalone (no pytest needed) and use direct function calls,
not HTTP, so they work without a running server.

Scenarios:
  1. Greeting → welcome + discovery question (0 LLM tokens)
  2. Vague opener → discovery question (0 LLM tokens)
  3. Off-topic → redirect message (0 LLM tokens)
  4. Signal-rich message → lead score increases
  5. Qualified lead → consultation offer triggered
  6. Booking intent → BOOK_CALL action chosen
"""
from __future__ import annotations

import sys
import os

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import conversation_state as cs_store
from services.conversation_state import ConversationState, CONSULTATION_OFFER_THRESHOLD
from services.decision_engine import AgentAction, decide

_PASS = "✅ PASS"
_FAIL = "❌ FAIL"
_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = _PASS if condition else _FAIL
    print(f"  {status}  {label}" + (f"  [{detail}]" if detail else ""))
    _results.append((label, condition))


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — Greeting → ASK_DISCOVERY_QUESTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 1: Greeting ──────────────────────────────────────")
state = ConversationState()
action = decide("Hi", state)
check("Greeting → ASK_DISCOVERY_QUESTION",
      action == AgentAction.ASK_DISCOVERY_QUESTION,
      f"got {action}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — Vague opener with no context → ASK_DISCOVERY_QUESTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 2: Vague opener ──────────────────────────────────")
state2 = ConversationState()
action2 = decide("I want to build something", state2)
check("Vague opener → ASK_DISCOVERY_QUESTION",
      action2 == AgentAction.ASK_DISCOVERY_QUESTION,
      f"got {action2}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — Off-topic → REDIRECT_TO_DOMAIN
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 3: Off-topic query ───────────────────────────────")
off_topics = [
    "What's a good recipe for pasta?",
    "Who won the cricket match?",
    "Tell me a joke",
    "What's the weather today?",
]
for q in off_topics:
    state_ot = ConversationState()
    action_ot = decide(q, state_ot)
    check(f"Off-topic redirect: '{q[:40]}'",
          action_ot == AgentAction.REDIRECT_TO_DOMAIN,
          f"got {action_ot}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4 — Signal extraction raises lead score
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 4: Lead score accumulation ───────────────────────")
state4 = ConversationState()
check("Initial lead score is 0", state4.lead_score == 0)

state4.update_from_message("I'm building a healthcare AI startup")
check("Industry extracted: healthcare",
      state4.industry == "healthcare",
      f"got {state4.industry}")
check("Lead score > 0 after industry", state4.lead_score > 0,
      f"score={state4.lead_score}")

state4.update_from_message("We need an MVP ready in 3 months with a $60k budget")
check("Budget extracted", state4.budget is not None, f"got {state4.budget}")
check("Timeline extracted", state4.timeline is not None, f"got {state4.timeline}")
check(f"Lead score ≥ threshold ({CONSULTATION_OFFER_THRESHOLD}) after budget+timeline",
      state4.lead_score >= CONSULTATION_OFFER_THRESHOLD,
      f"score={state4.lead_score}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 5 — Qualified lead → OFFER_CONSULTATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 5: Qualified lead → consultation offer ───────────")
state5 = ConversationState()
state5.update_from_message("We have a healthcare product idea")
state5.update_from_message("Our budget is $80k and we want to launch in 4 months")
state5.update_from_message("We are at seed stage and serve enterprise hospitals")

action5 = decide("How should we approach the development?", state5)
check(f"Qualified lead → OFFER_CONSULTATION",
      action5 == AgentAction.OFFER_CONSULTATION,
      f"got {action5}, score={state5.lead_score}")

# Offer should not be repeated
state5.consultation_offered = True
action5b = decide("And what about the tech stack?", state5)
check("Offer not repeated after first offer",
      action5b != AgentAction.OFFER_CONSULTATION,
      f"got {action5b}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 6 — Booking intent → BOOK_CALL
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 6: Booking intent → BOOK_CALL ────────────────────")
state6 = ConversationState()
state6.turn_count = 3  # simulate mid-conversation
booking_queries = [
    "Can we schedule a call?",
    "I'd like to book a meeting with your team",
    "Set up a 30 minute call please",
]
for bq in booking_queries:
    action_b = decide(bq, state6)
    check(f"Booking intent: '{bq[:40]}'",
          action_b == AgentAction.BOOK_CALL,
          f"got {action_b}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 7 — Rolling summary helpers
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Scenario 7: Conversation state context snippet ────────────")
state7 = ConversationState()
state7.industry      = "fintech"
state7.project_type  = "mvp"
state7.budget        = "$50k"
state7.timeline      = "3 months"
state7.conversation_summary = "User wants a fintech MVP for B2B payments."

snippet = state7.to_context_snippet()
check("Context snippet generated",
      bool(snippet) and "fintech" in snippet,
      f"snippet='{snippet[:80]}'")
check("Budget in snippet", "$50k" in snippet)
check("Summary in snippet", "fintech MVP" in snippet)


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in _results if ok)
total  = len(_results)
print(f"\n{'='*60}")
print(f"Results: {passed}/{total} tests passed")
if passed == total:
    print("🎉 All tests passed!")
else:
    failed = [label for label, ok in _results if not ok]
    print("❌ Failed tests:")
    for f in failed:
        print(f"   - {f}")
    sys.exit(1)
