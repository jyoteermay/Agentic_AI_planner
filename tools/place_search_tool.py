import os
from utils.place_info_search import GooglePlaceSearchTool, TavilyPlaceSearchTool
from typing import List
from langchain.tools import tool
from dotenv import load_dotenv
from logger.logging import get_logger

logger = get_logger(__name__)

class PlaceSearchTool:
    def __init__(self):
        load_dotenv()
        self.google_api_key = os.environ.get("GPLACES_API_KEY")
        # Google Places is skipped unless USE_GOOGLE_PLACES=1 (the key currently gets REQUEST_DENIED)
        self.use_google = os.getenv("USE_GOOGLE_PLACES") == "1" and bool(self.google_api_key)
        self.google_places_search = GooglePlaceSearchTool(self.google_api_key) if self.use_google else None
        self.tavily_search = TavilyPlaceSearchTool()
        self.place_search_tool_list = self._setup_tools()
        logger.info("Place search source: %s", "Google Places (Tavily fallback)" if self.use_google else "Tavily")

    def _search(self, place: str, label: str, google_fn, tavily_fn) -> str:
        """Try Google Places (if enabled), otherwise / on failure use Tavily."""
        if self.use_google:
            try:
                result = google_fn(place)
                if result:
                    return f"Following are the {label} {place} as suggested by google: {result}"
                logger.warning("Google Places returned nothing for %s; using Tavily", place)
            except Exception as e:
                logger.warning("Google Places failed for %s (%s); falling back to Tavily", place, e)
        return f"Following are the {label} {place}: {tavily_fn(place)}"

    def _setup_tools(self) -> List:
        """Setup all tools for the place search tool"""
        g, t = self.google_places_search, self.tavily_search

        @tool
        def search_attractions(place:str) -> str:
            """Search attractions of a place"""
            return self._search(place, "attractions of", g and g.google_search_attractions, t.tavily_search_attractions)

        @tool
        def search_restaurants(place:str) -> str:
            """Search restaurants of a place"""
            return self._search(place, "restaurants of", g and g.google_search_restaurants, t.tavily_search_restaurants)

        @tool
        def search_activities(place:str) -> str:
            """Search activities of a place"""
            return self._search(place, "activities in and around", g and g.google_search_activity, t.tavily_search_activity)

        @tool
        def search_transportation(place:str) -> str:
            """Search transportation of a place"""
            return self._search(place, "modes of transportation available in", g and g.google_search_transportation, t.tavily_search_transportation)

        return [search_attractions, search_restaurants, search_activities, search_transportation]
