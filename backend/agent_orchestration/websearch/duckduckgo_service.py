"""
DuckDuckGo Search Service
=========================

Provides web search functionality using DuckDuckGo.
No API key required - uses the ddgs library (formerly duckduckgo-search).
"""

import logging
from typing import Dict, List, Any, Optional
from django.conf import settings

logger = logging.getLogger('agent_orchestration')


class DuckDuckGoService:
    """
    Web search service using DuckDuckGo.
    Supports general search and domain-restricted search.
    """
    
    DEFAULT_MAX_RESULTS = 5
    
    def __init__(self):
        """Initialize the DuckDuckGo service."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.default_max_results = websearch_config.get('MAX_RESULTS', self.DEFAULT_MAX_RESULTS)
        logger.info(f"🔍 DUCKDUCKGO SERVICE: Initialized (default max results: {self.default_max_results})")
    
    def _get_ddgs_class(self):
        """
        Get the DDGS class from either the new 'ddgs' package or legacy 'duckduckgo_search'.
        Returns the class or None if neither is available.
        """
        # Try new package name first
        try:
            from ddgs import DDGS
            return DDGS
        except ImportError:
            pass
        
        # Fall back to old package name
        try:
            from duckduckgo_search import DDGS
            return DDGS
        except ImportError:
            pass
        
        logger.error("❌ DUCKDUCKGO: Neither 'ddgs' nor 'duckduckgo-search' package is installed. Run: pip install ddgs")
        return None
    
    def search(
        self, 
        query: str, 
        max_results: Optional[int] = None,
        domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform a DuckDuckGo search.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            domains: Optional list of domains to restrict search to
            
        Returns:
            List of search result dicts with title, url, body (snippet)
        """
        DDGS = self._get_ddgs_class()
        if DDGS is None:
            return []
        
        effective_max_results = max_results or self.default_max_results
        
        # Build the search query
        search_query = query
        if domains:
            # Append site: operators to restrict search to specific domains
            domain_operators = " OR ".join(f"site:{domain}" for domain in domains)
            search_query = f"{query} ({domain_operators})"
            logger.info(f"🔍 DUCKDUCKGO: Domain-restricted search - domains: {domains}")
        
        logger.info(f"🔍 DUCKDUCKGO: Searching for '{query[:50]}...' (max results: {effective_max_results})")
        
        try:
            with DDGS() as ddgs:
                # Perform text search
                raw_results = list(ddgs.text(
                    search_query, 
                    max_results=effective_max_results
                ))
            
            logger.info(f"🔍 DUCKDUCKGO: Raw results count: {len(raw_results)}")
            if raw_results:
                logger.debug(f"🔍 DUCKDUCKGO: First raw result: {raw_results[0]}")
            
            # Format results
            formatted_results = self._format_results(raw_results)
            
            logger.info(f"✅ DUCKDUCKGO: Found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ DUCKDUCKGO: Search failed: {e}", exc_info=True)
            return []
    
    def search_news(
        self, 
        query: str, 
        max_results: Optional[int] = None,
        timelimit: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform a DuckDuckGo news search.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            timelimit: Time limit for results ('d' = day, 'w' = week, 'm' = month)
            
        Returns:
            List of news result dicts
        """
        DDGS = self._get_ddgs_class()
        if DDGS is None:
            return []
        
        effective_max_results = max_results or self.default_max_results
        
        logger.info(f"📰 DUCKDUCKGO NEWS: Searching for '{query[:50]}...'")
        
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.news(
                    query, 
                    max_results=effective_max_results,
                    timelimit=timelimit
                ))
            
            # Format news results
            formatted_results = self._format_news_results(raw_results)
            
            logger.info(f"✅ DUCKDUCKGO NEWS: Found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ DUCKDUCKGO NEWS: Search failed: {e}", exc_info=True)
            return []
    
    def _format_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format raw DuckDuckGo results into a standardized format.
        
        Args:
            raw_results: Raw results from duckduckgo-search
            
        Returns:
            List of formatted result dicts
        """
        formatted = []
        
        for i, result in enumerate(raw_results):
            formatted.append({
                'rank': i + 1,
                'title': result.get('title', ''),
                'url': result.get('href', result.get('link', '')),
                'snippet': result.get('body', result.get('description', '')),
                'source': 'duckduckgo',
                'metadata': {
                    'raw_result': result
                }
            })
        
        return formatted
    
    def _format_news_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format raw DuckDuckGo news results.
        
        Args:
            raw_results: Raw news results
            
        Returns:
            List of formatted news result dicts
        """
        formatted = []
        
        for i, result in enumerate(raw_results):
            formatted.append({
                'rank': i + 1,
                'title': result.get('title', ''),
                'url': result.get('url', result.get('link', '')),
                'snippet': result.get('body', result.get('excerpt', '')),
                'source': result.get('source', 'unknown'),
                'date': result.get('date', ''),
                'image': result.get('image', ''),
                'metadata': {
                    'raw_result': result
                }
            })
        
        return formatted
    
    def format_results_for_context(
        self, 
        results: List[Dict[str, Any]], 
        include_urls: bool = True
    ) -> str:
        """
        Format search results into a text context for agent consumption.
        
        Args:
            results: List of search result dicts
            include_urls: Whether to include URLs in the formatted output
            
        Returns:
            Formatted text string suitable for agent context
        """
        if not results:
            return "No search results found."
        
        formatted_parts = []
        formatted_parts.append(f"Found {len(results)} web search results:\n")
        
        for result in results:
            rank = result.get('rank', '?')
            title = result.get('title', 'Untitled')
            snippet = result.get('snippet', '')
            url = result.get('url', '')
            
            result_text = f"[{rank}] {title}"
            if include_urls and url:
                result_text += f"\n    URL: {url}"
            if snippet:
                result_text += f"\n    {snippet}"
            
            formatted_parts.append(result_text)
        
        return "\n\n".join(formatted_parts)
