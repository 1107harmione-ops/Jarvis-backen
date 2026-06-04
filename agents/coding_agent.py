import subprocess, sys, os, tempfile, re, time
from agents.base_agent import BaseAgent
from core.config import GROQ_CODING_MODEL

class CodingAgent(BaseAgent):
    name = "CodingAgent"
    description = "Writes, runs, fixes and explains code in any programming language"
    model = GROQ_CODING_MODEL
    max_tokens = 4096
    temperature = 0.2

    CODE_SYSTEM = """You are an expert software engineer. When asked to write code:
- Write clean, working, well-commented code
- Always wrap code in ```language ... ``` blocks
- After the code, add a brief explanation of what it does
- For errors/bugs: explain the fix clearly before showing corrected code
- Support: Python, JavaScript, Java, C++, C, Dart, Kotlin, Swift, Go, Rust, SQL, HTML/CSS, Bash
"""

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        query_lower = query.lower()
        if any(k in query_lower for k in ["run ", "execute ", "output of", "what does this code"]):
            return self._run_and_explain(query, parameters)
        elif any(k in query_lower for k in ["fix", "debug", "error", "bug", "broken", "not working"]):
            return self._debug_code(query, parameters)
        elif any(k in query_lower for k in ["explain", "what is", "how does", "understand"]):
            return self._explain_code(query, parameters)
        elif any(k in query_lower for k in ["improve", "optimize", "refactor", "better"]):
            return self._improve_code(query, parameters)
        else:
            return self._write_code(query, parameters)

    def _write_code(self, query: str, parameters: dict) -> dict:
        lang = parameters.get("language", "")
        lang_hint = f"Use {lang}." if lang else "Use the most appropriate language."
        response = self._ask([{"role": "user", "content": f"Write code to: {query}\n{lang_hint}"}], system=self.CODE_SYSTEM)
        code, lang_detected = self._extract_code(response)
        execution_result = None
        run_auto = parameters.get("auto_run", False)
        if run_auto and code and lang_detected in ("python", "py", "python3"):
            execution_result = self._execute_python(code, timeout=10)
        return self._ok(response, metadata={"task": "write_code", "language": lang_detected or lang or "auto", "code_extracted": bool(code), "execution": execution_result})

    def _explain_code(self, query: str, parameters: dict) -> dict:
        response = self._ask([{"role": "user", "content": f"Explain this code clearly, step by step:\n\n{query}\n\nBreak it down: what each part does, the overall purpose, and any important patterns used."}], system=self.CODE_SYSTEM)
        return self._ok(response, metadata={"task": "explain_code"})

    def _debug_code(self, query: str, parameters: dict) -> dict:
        response = self._ask([{"role": "user", "content": f"Debug and fix this code:\n\n{query}\n\n1. Identify the bug(s)\n2. Explain why it was wrong\n3. Show the corrected code"}], system=self.CODE_SYSTEM)
        return self._ok(response, metadata={"task": "debug_code"})

    def _improve_code(self, query: str, parameters: dict) -> dict:
        response = self._ask([{"role": "user", "content": f"Improve and optimize this code:\n\n{query}\n\nFocus on: readability, performance, best practices, and any potential bugs."}], system=self.CODE_SYSTEM)
        return self._ok(response, metadata={"task": "improve_code"})

    def _run_and_explain(self, query: str, parameters: dict) -> dict:
        code, lang = self._extract_code(query)
        if not code:
            if "print(" in query or "def " in query or "import " in query:
                code = query
                lang = "python"
        if code and lang in ("python", "py", "python3", ""):
            exec_result = self._execute_python(code, timeout=10)
            explanation = self._ask([{"role": "user", "content": f"This Python code was run:\n```python\n{code}\n```\nOutput was:\n{exec_result}\n\nExplain what the code does and what the output means."}], system=self.CODE_SYSTEM)
            return self._ok(explanation, metadata={"task": "run_code", "execution_output": exec_result, "code": code})
        else:
            response = self._ask([{"role": "user", "content": f"Explain the output/behavior of this code:\n{query}"}], system=self.CODE_SYSTEM)
            return self._ok(response, metadata={"task": "explain_output"})

    def _extract_code(self, text: str):
        m = re.search(r"```(\w*)\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(2).strip(), m.group(1).lower().strip()
        return None, None

    def _execute_python(self, code: str, timeout: int = 10) -> str:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name
            result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=timeout)
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            output = f"[Execution timed out after {timeout} seconds]"
        except Exception as e:
            output = f"[Execution error: {e}]"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return output
