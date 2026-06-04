import re, json, requests
from agents.base_agent import BaseAgent
from core.config import SERP_API_KEY, GROQ_CODING_MODEL

_http = requests.Session()
_http.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36"})

class ResearchAgent(BaseAgent):
    name = "ResearchAgent"
    description = "Multi-source research: searches web, reads pages, synthesizes answers with citations"
    model = GROQ_CODING_MODEL
    max_tokens = 4096
    temperature = 0.2

    SYNTH_SYSTEM = """You are a research analyst. Given multiple source excerpts about a topic,
synthesize a comprehensive, accurate, well-structured answer.
Format: Start with a clear answer, then provide details, then list key facts.
Cite sources inline like [Source 1]. Be factual and concise."""

    SUMMARIZE_SYSTEM = """Summarize this web page content in 3-5 sentences.
Focus on information relevant to the research topic.
Return only the summary, nothing else."""

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        num_sources = parameters.get("sources", 4)
        urls_data = self._search(query, num=num_sources)
        if not urls_data:
            return self._err(f"No search results found for: {query}")
        summaries = []
        sources = []
        for i, item in enumerate(urls_data[:num_sources], 1):
            url = item.get("link", "")
            title = item.get("title", f"Source {i}")
            snippet = item.get("snippet", "")
            content = self._fetch_page(url) or snippet
            if content:
                summary = self._summarize(content, query, source_num=i)
                summaries.append(f"[Source {i}] {title}:\n{summary}")
                sources.append({"num": i, "title": title, "url": url})
        if not summaries:
            return self._err("Could not retrieve content from any sources.")
        combined = "\n\n".join(summaries)
        final = self._ask([{"role": "user", "content": f"Research question: {query}\n\nSource summaries:\n{combined}\n\nProvide a comprehensive answer with citations."}], system=self.SYNTH_SYSTEM)
        source_lines = "\n".join([f"  [{s['num']}] {s['title']} — {s['url']}" for s in sources])
        return self._ok(f"{final}\n\nSources:\n{source_lines}", metadata={"task": "research", "query": query, "sources_found": len(sources), "sources": sources})

    def _search(self, query: str, num: int = 5) -> list:
        try:
            r = _http.get("https://serpapi.com/search", params={"q": query, "api_key": SERP_API_KEY, "num": num}, timeout=10)
            if r.status_code == 200:
                return r.json().get("organic_results", [])
        except Exception:
            pass
        return []

    def _fetch_page(self, url: str, max_chars: int = 4000) -> str:
        if not url or not url.startswith("http"):
            return ""
        try:
            resp = _http.get(url, timeout=8)
            if resp.status_code != 200:
                return ""
            html = resp.text
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
            except ImportError:
                text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
        except Exception:
            return ""

    def _summarize(self, content: str, query: str, source_num: int) -> str:
        try:
            summary = self._ask([{"role": "user", "content": f"Topic: {query}\n\nContent to summarize:\n{content[:3000]}"}], system=self.SUMMARIZE_SYSTEM, max_tokens=300, temperature=0.1)
            return summary if summary and not summary.startswith("[") else content[:400]
        except Exception:
            return content[:400]
