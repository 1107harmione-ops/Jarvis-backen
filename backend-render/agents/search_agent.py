import re
from agents.base_agent import BaseAgent
from core.config import SERP_API_KEY
import requests

_http = requests.Session()

class SearchAgent(BaseAgent):
    name = "SearchAgent"
    description = "Fast real-time web search: instant answers, news, prices, weather, facts"
    temperature = 0.1

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        q = query.lower()
        if any(w in q for w in ["news", "latest", "today", "breaking"]):
            return self._news_search(query)
        elif any(w in q for w in ["weather", "temperature", "forecast", "rain"]):
            return self._weather_search(query)
        elif any(w in q for w in ["price", "cost", "stock", "rate", "₹", "$", "usd", "inr"]):
            return self._price_search(query)
        elif any(w in q for w in ["score", "match", "cricket", "football", "ipl"]):
            return self._sports_search(query)
        else:
            return self._general_search(query)

    def _general_search(self, query: str) -> dict:
        data = self._serp(query)
        answer = self._extract_best_answer(data, query)
        sources = [{"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", "")} for item in data.get("organic_results", [])[:3]]
        return self._ok(answer, metadata={"task": "general_search", "query": query, "sources": sources})

    def _news_search(self, query: str) -> dict:
        data = self._serp(query, params={"tbm": "nws", "num": 5})
        news_results = data.get("news_results", data.get("organic_results", []))
        if not news_results:
            return self._err("No news found.")
        headlines = []
        sources = []
        for i, item in enumerate(news_results[:5], 1):
            title = item.get("title", "No title")
            source = item.get("source", {})
            source_name = source.get("name", "") if isinstance(source, dict) else str(source)
            url = item.get("link", "")
            date = item.get("date", "")
            headlines.append(f"{i}. {title} ({source_name}) {date}")
            sources.append({"title": title, "url": url})
        return self._ok("Latest News:\n" + "\n".join(headlines), metadata={"task": "news_search", "sources": sources})

    def _weather_search(self, query: str) -> dict:
        data = self._serp(query)
        weather = data.get("answer_box", {})
        if weather:
            parts = []
            if weather.get("location"): parts.append(f"Location: {weather['location']}")
            if weather.get("temperature"): parts.append(f"Temperature: {weather['temperature']}")
            if weather.get("weather"): parts.append(f"Weather: {weather['weather']}")
            if weather.get("humidity"): parts.append(f"Humidity: {weather['humidity']}")
            if weather.get("wind"): parts.append(f"Wind: {weather['wind']}")
            if parts:
                return self._ok("\n".join(parts), metadata={"task": "weather", "raw": weather})
        answer = self._extract_best_answer(data, query)
        return self._ok(answer, metadata={"task": "weather"})

    def _price_search(self, query: str) -> dict:
        data = self._serp(query)
        answer = self._extract_best_answer(data, query)
        kg = data.get("knowledge_graph", {})
        if kg:
            price = kg.get("price", "") or kg.get("stock_price", "")
            name = kg.get("title", "")
            if price:
                answer = f"{name}: {price}"
        return self._ok(answer, metadata={"task": "price_search"})

    def _sports_search(self, query: str) -> dict:
        data = self._serp(query)
        answer = self._extract_best_answer(data, query)
        sports_results = data.get("sports_results", {})
        if sports_results:
            game = sports_results.get("game_spotlight", {})
            if game:
                teams = game.get("teams", [])
                if len(teams) >= 2:
                    answer = f"{teams[0].get('name', 'Team 1')} {teams[0].get('score', '?')} — {teams[1].get('name', 'Team 2')} {teams[1].get('score', '?')}"
        return self._ok(answer, metadata={"task": "sports_search"})

    def _serp(self, query: str, params: dict = None) -> dict:
        p = {"q": query, "api_key": SERP_API_KEY}
        if params:
            p.update(params)
        try:
            r = _http.get("https://serpapi.com/search", params=p, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _extract_best_answer(self, data: dict, query: str) -> str:
        ab = data.get("answer_box", {})
        if ab.get("answer"): return str(ab["answer"])
        if ab.get("snippet"): return str(ab["snippet"])
        kg = data.get("knowledge_graph", {})
        if kg.get("description"): return kg["description"]
        results = data.get("organic_results", [])
        if results:
            snippets = [r.get("snippet", "") for r in results[:3] if r.get("snippet")]
            if snippets:
                return " ".join(snippets[:2])
        return f"No direct answer found for: {query}"
