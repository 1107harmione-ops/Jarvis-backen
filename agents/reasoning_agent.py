from agents.base_agent import BaseAgent
from core.config import GROQ_COMPOUND_MODEL

class ReasoningAgent(BaseAgent):
    name = "ReasoningAgent"
    description = "Step-by-step reasoning: math, planning, analysis, pros/cons, decisions"
    model = GROQ_COMPOUND_MODEL
    max_tokens = 4096
    temperature = 0.1

    REASONING_SYSTEM = """You are a systematic analytical thinker. For every problem:
1. Break it down into clear steps
2. Show your reasoning at each step
3. State any assumptions
4. Give a definitive, actionable final answer
5. Rate your confidence (High/Medium/Low)
Format your response:
**Understanding:** [what is being asked]
**Steps:**
  Step 1: [...]
  Step 2: [...]
**Answer:** [clear final answer]
**Confidence:** High/Medium/Low"""

    MATH_SYSTEM = """You are a precise mathematics solver.
- Show every calculation step
- Use clear notation
- Verify your answer at the end
Format:
**Problem:** [restate clearly]
**Solution:**
  Step 1: [...]
  Step 2: [...]
**Final Answer:** [bold the answer]
**Verification:** [check the answer]"""

    PLAN_SYSTEM = """You are a strategic planner.
Break the goal into a realistic, actionable plan:
- Phase 1, Phase 2, Phase 3 structure
- Each phase has specific tasks
- Include time estimates
- Identify key risks and how to mitigate them
- List required resources"""

    DECISION_SYSTEM = """You are an objective decision-making advisor.
For every decision:
1. Clarify the decision to be made
2. List all viable options
3. For each option: pros, cons, risks
4. Recommend the best option with clear reasoning
5. State what information would change the recommendation"""

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        q = query.lower()
        if any(w in q for w in ["calculate", "math", "solve", "equation", "compute", "how much", "percentage", "formula", "algebra"]):
            return self._math(query)
        elif any(w in q for w in ["plan", "roadmap", "steps to", "how to achieve", "strategy", "goal", "schedule", "timeline"]):
            return self._plan(query)
        elif any(w in q for w in ["should i", "which is better", "compare", "pros and cons", "decide", "choice", "option"]):
            return self._decide(query)
        elif any(w in q for w in ["analyze", "analyse", "why", "explain why", "reason", "cause", "effect", "impact"]):
            return self._analyze(query)
        else:
            return self._general_reason(query)

    def _math(self, query: str) -> dict:
        response = self._ask([{"role": "user", "content": query}], system=self.MATH_SYSTEM)
        return self._ok(response, metadata={"task": "math_solve"})

    def _plan(self, query: str) -> dict:
        response = self._ask([{"role": "user", "content": f"Create a detailed plan for: {query}"}], system=self.PLAN_SYSTEM)
        return self._ok(response, metadata={"task": "planning"})

    def _decide(self, query: str) -> dict:
        response = self._ask([{"role": "user", "content": f"Help me decide: {query}"}], system=self.DECISION_SYSTEM)
        return self._ok(response, metadata={"task": "decision"})

    def _analyze(self, query: str) -> dict:
        response = self._ask([{"role": "user", "content": f"Analyze this thoroughly with reasoning: {query}"}], system=self.REASONING_SYSTEM)
        return self._ok(response, metadata={"task": "analysis"})

    def _general_reason(self, query: str) -> dict:
        response = self._ask([{"role": "user", "content": query}], system=self.REASONING_SYSTEM)
        return self._ok(response, metadata={"task": "general_reasoning"})
