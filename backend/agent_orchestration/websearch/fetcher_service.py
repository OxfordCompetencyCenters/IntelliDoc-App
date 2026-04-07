"""
Website Fetcher Service
=======================

Provides parallel URL fetching with content extraction using aiohttp and BeautifulSoup.
Designed for efficient retrieval of multiple web pages concurrently.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup, NavigableString, Tag
from django.conf import settings

logger = logging.getLogger('agent_orchestration')


@dataclass
class PageSection:
    """
    Single section of a web page. This is part of the canonical
    PageCapture representation – not a secondary cache layer.
    """
    type: str  # heading|paragraph|list|table|code|other
    level: Optional[int] = None  # for headings
    text: str = ""
    html_snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PageCapture:
    """
    Canonical, single-source-of-truth representation of a fetched URL.
    All downstream views (LLM context, summaries, etc.) are derived
    from this structure and not stored separately.
    """
    url: str
    final_url: Optional[str] = None
    domain: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    raw_html: Optional[str] = None
    raw_html_size: int = 0
    raw_html_truncated: bool = False
    sections: List[PageSection] = field(default_factory=list)
    word_count: int = 0
    truncated: bool = False  # text-level truncation flag
    extraction_error: Optional[str] = None
    anchor_fragment: Optional[str] = None  # the #fragment from the original URL, if any

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PageCapture to a JSON-serialisable dict for caching.
        """
        data = asdict(self)
        # dataclasses.asdict already converts nested dataclasses
        return data


class WebsiteFetcherService:
    """
    Service for fetching and extracting content from web pages.
    Supports parallel fetching of multiple URLs using asyncio.
    """

    # Default configuration
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_CONTENT_LENGTH = 100000  # characters (LLM-oriented text cap)
    DEFAULT_MAX_HTML_BYTES = 2_000_000  # 2 MB raw HTML cap

    # User agent to avoid being blocked
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Tags to remove from content (only for derived text, not raw_html)
    REMOVE_TAGS = [
        'script', 'style', 'noscript',
        # Structural chrome — never contain primary article content
        'nav', 'header', 'footer', 'aside',
        'form',        # search boxes, login forms
        'menu',
        'figure',      # image captions fragment LLM context
        'figcaption',
    ]

    # CSS classes/IDs often associated with non-content elements.
    REMOVE_PATTERNS = [
        r'advertisement', r'\bad[-_]', r'\bads[-_]', r'[-_]ads\b',
        r'cookie', r'popup', r'modal', r'overlay',
        r'nav(igation|bar)?[-_\s]', r'[-_]nav\b',
        r'sidebar', r'side[-_]bar',
        r'widget[-_](area|zone|section|sidebar)',  # scoped — r'widget' alone was too broad
        r'breadcrumb', r'site[-_]header', r'site[-_]footer',
        r'social[-_]', r'share[-_]', r'sharing',
        r'related[-_]', r'recommended[-_]', r'also[-_]read',
        r'comment(s)?[-_]', r'discussion[-_]',
        r'menu[-_]', r'[-_]menu\b',
        r'banner[-_]', r'promo[-_]',
        r'toc\b', r'table[-_]of[-_]contents',
    ]

    # Minimum heading text length — reduced to 3 to preserve short but valid headings
    # like "API", "FAQ", "Usage", "Setup", "Overview", "Reference", etc.
    MIN_HEADING_LEN = 3

    # Element-type sets used in single-pass traversal
    HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    BLOCK_EXTRACT_TAGS = {'ul', 'ol', 'table', 'pre'}
    # Paragraph tags inside these block parents are captured via the parent
    INLINE_SKIP_PARENTS = {'li', 'td', 'th', 'pre'}

    # Known SPA mount-point IDs (client-side-rendered pages)
    SPA_MOUNT_IDS = {'__next', '__nuxt', '__gatsby', 'app', 'root', '__app'}

    # -------------------------------------------------------------------------
    # Content-root detection regexes
    # Expanded to cover common documentation frameworks:
    #   Docusaurus, MkDocs/Material, GitBook, VitePress, Sphinx,
    #   GitHub markdown, Confluence, Notion, ReadTheDocs, Hexo, Hugo
    # -------------------------------------------------------------------------
    _CONTENT_ID_RE = re.compile(
        r'\b('
        # Generic
        r'content|main|article|post[-_]?body|entry[-_]?content'
        r'|story[-_]?body|article[-_]?body|page[-_]?content'
        # GitBook / generic
        r'|page[-_]?body|page[-_]?inner|article[-_]?inner'
        # Doc frameworks
        r'|doc[-_]?content|doc[-_]?body|doc[-_]?main'
        r')\b',
        re.I,
    )
    _CONTENT_CLASS_RE = re.compile(
        r'(^|\s)('
        # ---- Existing ----
        r'article|entry|post|story|prose|richtext'
        r'|article[-_]body|post[-_]body|entry[-_]content'
        r'|main[-_]content|page[-_]content|content[-_]body'
        # ---- Docusaurus v2/v3 ----
        r'|theme[-_]doc[-_]markdown|docMainContainer|docItemContainer|docItemCol'
        # ---- MkDocs / Material for MkDocs ----
        r'|md[-_]content|md[-_]main__inner|md[-_]typeset'
        # ---- GitBook ----
        r'|page[-_]body|page[-_]inner|gitbook[-_]root'
        # ---- VitePress ----
        r'|vp[-_]doc'
        # ---- Sphinx ----
        r'|documentwrapper|bodywrapper'
        # ---- GitHub rendered markdown ----
        r'|markdown[-_]body|blob[-_]wrapper'
        # ---- Confluence ----
        r'|wiki[-_]content|aui[-_]page[-_]panel[-_]content'
        # ---- Notion (public pages, not SPA) ----
        r'|notion[-_]page[-_]content'
        # ---- ReadTheDocs / RST ----
        r'|rstdoc|rst[-_]content'
        # ---- Hexo / Hugo ----
        r'|article[-_]inner|article[-_]content|single'
        r')(\s|$)',
        re.I,
    )

    def __init__(self):
        """Initialize fetcher with settings from Django config."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.timeout = websearch_config.get('REQUEST_TIMEOUT', self.DEFAULT_TIMEOUT)
        self.max_content_length = websearch_config.get('MAX_CONTENT_LENGTH', self.DEFAULT_MAX_CONTENT_LENGTH)
        self.max_html_bytes = websearch_config.get('MAX_HTML_BYTES', self.DEFAULT_MAX_HTML_BYTES)
        logger.info(
            f"🌐 WEBSITE FETCHER: Initialized "
            f"(timeout: {self.timeout}s, max_content: {self.max_content_length} chars, "
            f"max_html_bytes: {self.max_html_bytes})"
        )

    # =========================================================================
    # Main Public Methods
    # =========================================================================

    async def fetch_urls_parallel(
        self,
        urls: List[str],
        timeout: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs in parallel using aiohttp.

        Args:
            urls: List of URLs to fetch
            timeout: Optional timeout override per request

        Returns:
            List of PageCapture dicts, one per URL, in the same order
        """
        if not urls:
            return []

        effective_timeout = timeout or self.timeout
        logger.info(f"🌐 WEBSITE FETCHER: Fetching {len(urls)} URLs in parallel (timeout: {effective_timeout}s)")

        # Create timeout configuration
        client_timeout = aiohttp.ClientTimeout(total=effective_timeout)

        # Configure headers
        headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

        async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
            # Create tasks for all URLs
            tasks = [self._fetch_single(session, url) for url in urls]

            # Execute all tasks in parallel, capturing exceptions
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to error dicts
        processed_results: List[Dict[str, Any]] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"❌ WEBSITE FETCHER: Failed to fetch {url}: {result}")
                capture = PageCapture(
                    url=url,
                    extraction_error=str(result),
                )
                processed_results.append(capture.to_dict())
            else:
                processed_results.append(result)

        # Count successes by absence of extraction_error (PageCapture never sets a 'success' key)
        successful = sum(1 for r in processed_results if not r.get('extraction_error'))
        logger.info(f"✅ WEBSITE FETCHER: Completed {successful}/{len(urls)} URLs successfully")

        return processed_results

    async def fetch_single_url(self, url: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch a single URL.

        Args:
            url: URL to fetch
            timeout: Optional timeout override

        Returns:
            PageCapture dict
        """
        results = await self.fetch_urls_parallel([url], timeout)
        if results:
            return results[0]
        capture = PageCapture(
            url=url,
            extraction_error='No results returned',
        )
        return capture.to_dict()

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _fetch_single(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """
        Fetch a single URL using the provided session.

        Args:
            session: aiohttp ClientSession
            url: URL to fetch (may include a #fragment)

        Returns:
            PageCapture dict with extracted data
        """
        try:
            logger.debug(f"🌐 FETCHING: {url}")

            # Parse fragment before the HTTP request — browsers never send fragments
            # to the server, but we use them post-parse to narrow extraction scope.
            parsed_url = urlparse(url)
            fragment = parsed_url.fragment or None
            fetch_url = urlunparse(parsed_url._replace(fragment='')) if fragment else url

            async with session.get(fetch_url, allow_redirects=True) as response:
                status = response.status
                content_type = response.headers.get('Content-Type', '')
                final_url = str(response.url)

                capture = PageCapture(
                    url=url,
                    final_url=final_url,
                    status_code=status,
                    content_type=content_type,
                    domain=urlparse(url).netloc,
                    anchor_fragment=fragment,
                )

                # Non-200 responses: record metadata but do not attempt extraction
                if status != 200:
                    capture.extraction_error = f"HTTP {status}: {response.reason}"
                    return capture.to_dict()

                # Only handle HTML/XHTML for now
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    capture.extraction_error = f"Non-HTML content type: {content_type}"
                    return capture.to_dict()

                # Read raw HTML (with byte cap)
                raw_bytes = await response.read()
                capture.raw_html_size = len(raw_bytes)
                if len(raw_bytes) > self.max_html_bytes:
                    capture.raw_html_truncated = True
                    raw_bytes = raw_bytes[: self.max_html_bytes]
                try:
                    html = raw_bytes.decode(response.charset or 'utf-8', errors='replace')
                except Exception:
                    html = raw_bytes.decode('utf-8', errors='replace')
                capture.raw_html = html

                # Parse HTML and populate sections + derived text metadata
                self._populate_from_html(capture, html, fragment=fragment)

                return capture.to_dict()

        except asyncio.TimeoutError:
            capture = PageCapture(
                url=url,
                extraction_error='Request timed out',
            )
            return capture.to_dict()
        except aiohttp.ClientError as e:
            capture = PageCapture(
                url=url,
                extraction_error=f"Client error: {str(e)}",
            )
            return capture.to_dict()
        except Exception as e:
            capture = PageCapture(
                url=url,
                extraction_error=f"Unexpected error: {str(e)}",
            )
            logger.error(f"❌ CONTENT FETCH: Failed for {url}: {e}")
            return capture.to_dict()

    # =========================================================================
    # Content Root Detection
    # =========================================================================

    def _find_content_root(self, soup: BeautifulSoup):
        """
        Return the most specific main-content container in the soup.

        Detection tiers (first match wins):
          Tier 1 — semantic/ARIA: <article>, <main>, role="main", id/class regexes
          Tier 2 — Schema.org:    itemprop="articleBody"
          Fallback — <body> or the full soup
        """
        # Tier 1: semantic tags + ARIA + id/class regexes
        candidate = (
            soup.find('article')
            or soup.find('main')
            or soup.find(attrs={'role': 'main'})
            or soup.find(id=self._CONTENT_ID_RE)
            or soup.find(class_=self._CONTENT_CLASS_RE)
        )
        if candidate:
            return candidate

        # Tier 2: Schema.org structured data (used by many CMS platforms)
        candidate = soup.find(attrs={'itemprop': 'articleBody'})
        if candidate:
            return candidate

        return soup.body or soup

    # =========================================================================
    # SPA / JavaScript Detection
    # =========================================================================

    def _detect_spa(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Return a descriptive warning string if the page appears to be a
        JavaScript SPA that rendered no meaningful content server-side.

        Heuristics (all must match):
          1. Body visible text < 300 chars
          2. >= 3 external <script src=...> tags (bundled JS app)
          3. A known SPA mount-point id is present
        """
        body = soup.body
        if not body:
            return None

        script_tags = soup.find_all('script', src=True)
        if len(script_tags) < 3:
            return None

        body_text = body.get_text(separator=' ', strip=True)
        if len(body_text) >= 300:
            return None  # Enough static content — not a blocking SPA

        # Check for known SPA mount points
        for spa_id in self.SPA_MOUNT_IDS:
            if soup.find(id=spa_id):
                return (
                    f"Page appears to be a JavaScript SPA (found #{spa_id} mount point "
                    f"with {len(script_tags)} script bundles but only {len(body_text)} chars "
                    f"of visible text). Static extraction returned no content. "
                    f"The page requires JavaScript execution to render its content."
                )

        # Generic fallback: many scripts + almost no text
        if len(body_text) < 100:
            return (
                f"Page appears to require JavaScript to render "
                f"({len(script_tags)} script bundles, {len(body_text)} chars visible text). "
                f"Static extraction returned no content."
            )

        return None

    # =========================================================================
    # Anchor Fragment Narrowing
    # =========================================================================

    def _find_fragment_root(
        self,
        soup: BeautifulSoup,
        content_root,
        fragment: str,
    ) -> Tuple[Optional[Any], Optional[int], Optional[Any]]:
        """
        Locate the element identified by #fragment and return a 3-tuple
        (start_node, stop_level, sibling_anchor_parent) that controls the
        single-pass traversal scope.

        Cases handled:
          1. Anchor IS a heading: <h2 id="...">Title</h2>
          2. Anchor inside a heading: <h2>Title <a id="...">¶</a></h2>  (Sphinx/Hugo)
          3. Non-empty container: <div id="..."><h2>...</h2><p>...</p></div>
          4. Empty anchor marker (Oxford/CMS): <a id="..."></a> before content block
          5. No heading in siblings — use first non-empty sibling as content_root
          6. Fallback to anchor's parent
          7. Fragment not found — full-page fallback

        Returns:
            (start_node, stop_level, sibling_anchor_parent)
            - stop_level=None + start_node set → replace content_root with start_node
            - stop_level set → traverse from start_node, stop at heading of that level
            - sibling_anchor_parent set → also stop at next empty <a id=...> at that parent
            - (None, None, None) → fragment not found, fall back to full page
        """
        # 1. Find by id= (most common)
        anchor = soup.find(id=fragment)
        if anchor is None:
            # Legacy: <a name="fragment"> — use a_tag itself (NOT a_tag.parent)
            a_tag = soup.find('a', attrs={'name': fragment})
            anchor = a_tag if a_tag else None
        if anchor is None:
            logger.debug(f"🔍 FRAGMENT: #{fragment} not found in page, using full page")
            return None, None, None

        # 2. Anchor IS a heading: <h2 id="...">Title</h2>
        if anchor.name in self.HEADING_TAGS:
            level = int(anchor.name[1])
            logger.debug(f"🔍 FRAGMENT: #{fragment} is heading h{level}")
            return anchor, level, None

        # 3. Anchor INSIDE a heading: <h2>Title <a id="...">¶</a></h2>  (Sphinx/Hugo)
        parent = anchor.parent
        if parent and parent.name in self.HEADING_TAGS:
            level = int(parent.name[1])
            logger.debug(f"🔍 FRAGMENT: #{fragment} is inside heading h{level}")
            return parent, level, None

        # 4. Non-empty container: <div id="..."><h2>...</h2><p>...</p></div>
        if anchor.get_text(strip=True):
            logger.debug(f"🔍 FRAGMENT: #{fragment} is non-empty <{anchor.name}>, using as content_root")
            return anchor, None, None

        # 5. Empty anchor marker (Oxford/CMS pattern):
        #    <a id="Section"></a> placed BEFORE the content block.
        #    Search following siblings for the first heading, stopping at the next marker.
        sibling_anchor_parent = anchor.parent
        for sibling in anchor.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            # Stop searching at the next empty anchor marker (next section boundary)
            if (sibling.name == 'a'
                    and sibling.get('id')
                    and not sibling.get_text(strip=True)):
                break
            # Direct heading sibling
            if sibling.name in self.HEADING_TAGS:
                logger.debug(
                    f"🔍 FRAGMENT: #{fragment} is empty marker, "
                    f"found direct heading <{sibling.name}>"
                )
                return sibling, int(sibling.name[1]), sibling_anchor_parent
            # Heading nested inside a sibling container (e.g. <div class="faqmodule"><h2>)
            h = sibling.find(list(self.HEADING_TAGS))
            if h:
                logger.debug(
                    f"🔍 FRAGMENT: #{fragment} is empty marker, "
                    f"found nested heading <{h.name}> inside <{sibling.name}>"
                )
                return h, int(h.name[1]), sibling_anchor_parent

        # 6. No heading found in siblings — use first non-empty sibling as new content_root
        for sibling in anchor.next_siblings:
            if isinstance(sibling, Tag) and sibling.get_text(strip=True):
                logger.debug(f"🔍 FRAGMENT: #{fragment} no heading found, using first content sibling")
                return sibling, None, None

        # 7. Fallback: use anchor's parent if it has content
        if parent and parent.get_text(strip=True):
            logger.debug(f"🔍 FRAGMENT: #{fragment} fallback to parent <{parent.name}>")
            return parent, None, None

        logger.debug(f"🔍 FRAGMENT: #{fragment} no usable anchor found, using full page")
        return None, None, None

    # =========================================================================
    # Block Extraction Helper
    # =========================================================================

    def _extract_block(self, node: Tag, tag: str) -> Optional[PageSection]:
        """
        Extract a PageSection from a block-level container (ul, ol, table, pre).
        Returns None if the element has no meaningful content.
        """
        if tag in ('ul', 'ol'):
            items = [li.get_text(strip=True) for li in node.find_all('li')]
            items = [i for i in items if i]
            if not items:
                return None
            return PageSection(
                type='list',
                text='\n'.join(f"- {item}" for item in items),
                html_snippet=str(node)[:1000],
                metadata={'item_count': len(items)},
            )

        if tag == 'table':
            rows = []
            for tr in node.find_all('tr'):
                cells = [c.get_text(strip=True) for c in tr.find_all(['th', 'td'])]
                if cells:
                    rows.append(cells)
            if not rows:
                return None
            return PageSection(
                type='table',
                text='\n'.join(' | '.join(row) for row in rows),
                html_snippet=str(node)[:1000],
                metadata={'row_count': len(rows)},
            )

        if tag == 'pre':
            text = node.get_text('\n', strip=True)
            if not text:
                return None
            return PageSection(
                type='code',
                text=text,
                html_snippet=str(node)[:1000],
            )

        return None

    # =========================================================================
    # Single-Pass Document-Order Traversal
    # =========================================================================

    def _single_pass_traverse(
        self,
        content_root,
        start_node: Optional[Tag] = None,
        stop_at_heading_level: Optional[int] = None,
        stop_at_sibling_parent: Optional[Any] = None,
    ) -> List[PageSection]:
        """
        Walk content_root's descendants in document order, extracting PageSections
        without duplicating nested content.

        Args:
            content_root: BeautifulSoup element to traverse
            start_node: If set, skip all nodes before this one (anchor fragment support)
            stop_at_heading_level: If set, stop when a heading at this level or
                higher is encountered (used together with start_node for heading anchors)
            stop_at_sibling_parent: If set, stop when an empty <a id=...> whose
                .parent is this element is encountered — detects the next CMS-style
                section boundary (e.g. the next <a id="Codex"></a> marker)

        Returns:
            List of PageSection in document order — no type-grouping, no duplicates
        """
        sections: List[PageSection] = []
        # Track id() of already-captured Tag objects to avoid re-processing nested elements
        processed_ids: set = set()

        # Fragment activation: skip nodes until start_node is reached
        active = start_node is None

        for node in content_root.descendants:
            if not isinstance(node, Tag):
                continue  # skip NavigableString, Comment, ProcessingInstruction

            tag = node.name
            if not tag:
                continue

            # --- Fragment: activate on reaching start_node ---
            if not active:
                if node is start_node:
                    active = True
                else:
                    continue

            # --- Fragment: stop at a heading at same or higher level ---
            if stop_at_heading_level is not None and tag in self.HEADING_TAGS:
                level = int(tag[1])
                if level <= stop_at_heading_level and node is not start_node:
                    break

            # --- Fragment: stop at the next CMS-style empty anchor marker ---
            # e.g. <a id="Codex"></a> placed at the same parent level as the
            # original <a id="AdvancedFeatures"></a> that started this traversal
            if (stop_at_sibling_parent is not None
                    and tag == 'a'
                    and node is not start_node
                    and node.get('id')
                    and not node.get_text(strip=True)
                    and node.parent is stop_at_sibling_parent):
                break

            # --- Skip already-processed subtrees ---
            if id(node) in processed_ids:
                continue

            # =================================================================
            # Headings — always extracted, at document position
            # =================================================================
            if tag in self.HEADING_TAGS:
                text = node.get_text(strip=True)
                if text and len(text) >= self.MIN_HEADING_LEN:
                    sections.append(PageSection(
                        type='heading',
                        level=int(tag[1]),
                        text=text,
                        html_snippet=str(node)[:1000],
                    ))
                # Mark heading + all its descendants as processed
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Paragraphs — skip if inside a list item, table cell, or pre block
            # (those are captured as part of their parent block container)
            # =================================================================
            if tag == 'p':
                parent = node.parent
                skip = False
                while parent and parent is not content_root:
                    if parent.name in self.INLINE_SKIP_PARENTS:
                        skip = True
                        break
                    parent = parent.parent
                if skip:
                    continue
                text = node.get_text(strip=True)
                if text:
                    sections.append(PageSection(
                        type='paragraph',
                        text=text,
                        html_snippet=str(node)[:1000],
                    ))
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Block containers (ul, ol, table, pre) — capture whole subtree
            # =================================================================
            if tag in self.BLOCK_EXTRACT_TAGS:
                section = self._extract_block(node, tag)
                if section:
                    sections.append(section)
                # Mark entire subtree as processed (prevents double-extraction
                # of nested <p>, <li>, <code>, etc.)
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Inline <code> — skip if inside <pre> (already captured with pre block)
            # Also skip standalone inline code (sub-sentence fragments are too noisy)
            # =================================================================
            if tag == 'code':
                processed_ids.add(id(node))
                continue

        return sections

    # =========================================================================
    # HTML Parsing and Section Population
    # =========================================================================

    def _populate_from_html(
        self,
        capture: PageCapture,
        html: str,
        fragment: Optional[str] = None,
    ) -> None:
        """
        Populate a PageCapture instance from raw HTML using a single document-order
        traversal. Handles anchor fragments, SPA detection, and framework-specific
        content root detection.

        Args:
            capture: PageCapture instance to populate in-place
            html: Raw HTML string
            fragment: URL fragment (#anchor) to narrow extraction scope, or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # --- Title ---
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            capture.title = (title[:500] if title else capture.domain)

            # --- Meta description ---
            meta_description = ''
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag and meta_tag.get('content'):
                meta_description = meta_tag['content']
            capture.meta_description = meta_description[:500] if meta_description else None

            # --- Detect SPA before cleanup (needs script tags intact) ---
            spa_warning = self._detect_spa(soup)

            # --- Remove obviously non-content tags globally ---
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # --- Find main content root ---
            content_root = self._find_content_root(soup)
            logger.debug(
                f"🔍 CONTENT EXTRACT: content_root=<{getattr(content_root, 'name', '?')}> "
                f"for {capture.url}"
            )

            # --- Pattern-based junk removal (ads, sidebars, etc.) ---
            # Runs after content_root isolation to protect content containers.
            _full_body_fallback = content_root is soup.body or content_root is soup
            _protected_ids: set = {id(content_root)}
            for _anc in content_root.parents:
                if _anc.name:
                    _protected_ids.add(id(_anc))

            for pattern in self.REMOVE_PATTERNS:
                pat = re.compile(pattern, re.I)
                for element in list(soup.find_all(class_=pat)):
                    if _full_body_fallback:
                        element.decompose()
                    elif id(element) in _protected_ids:
                        pass
                    elif not element.find_parent(lambda t: t is content_root):  # noqa: B023
                        element.decompose()
                for element in list(soup.find_all(id=pat)):
                    if _full_body_fallback:
                        element.decompose()
                    elif id(element) in _protected_ids:
                        pass
                    elif not element.find_parent(lambda t: t is content_root):  # noqa: B023
                        element.decompose()

            # --- Anchor fragment narrowing ---
            traverse_start: Optional[Tag] = None
            traverse_stop_level: Optional[int] = None
            traverse_stop_sibling_parent = None

            if fragment:
                start_node, stop_level, sibling_anchor_parent = self._find_fragment_root(
                    soup, content_root, fragment
                )
                if start_node is not None:
                    if stop_level is None:
                        # Non-empty container or headingless sibling: replace content_root
                        content_root = start_node
                    else:
                        # Heading anchor or empty-marker anchor: traverse mode
                        traverse_start = start_node
                        traverse_stop_level = stop_level
                        traverse_stop_sibling_parent = sibling_anchor_parent  # may be None

            # --- Single-pass document-order traversal ---
            sections = self._single_pass_traverse(
                content_root,
                start_node=traverse_start,
                stop_at_heading_level=traverse_stop_level,
                stop_at_sibling_parent=traverse_stop_sibling_parent,
            )

            capture.sections = sections

            # If no content was extracted AND we detected a SPA, surface the warning
            if not sections and spa_warning:
                capture.extraction_error = spa_warning

            # --- Build flattened text for metrics and LLM context ---
            parts: List[str] = []
            for sec in sections:
                if sec.type == 'heading':
                    prefix = '#' * (sec.level or 1)
                    parts.append(f"{prefix} {sec.text}")
                else:
                    parts.append(sec.text)
            flat_text = '\n\n'.join(parts).strip()

            # Clean whitespace
            flat_text = re.sub(r'\n\s*\n', '\n\n', flat_text)
            flat_text = re.sub(r' +', ' ', flat_text)
            flat_text = flat_text.strip()

            # Truncate for LLM usage but keep flag
            if len(flat_text) > self.max_content_length:
                capture.truncated = True
                flat_text = flat_text[: self.max_content_length] + "... [truncated]"

            capture.word_count = len(flat_text.split()) if flat_text else 0

        except Exception as e:
            logger.error(f"❌ CONTENT EXTRACTION: Failed for {capture.url}: {e}")
            capture.extraction_error = str(e)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid and fetchable.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid
        """
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ('http', 'https'),
                parsed.netloc,
                len(url) < 2048  # Reasonable URL length limit
            ])
        except Exception:
            return False

    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL for consistent cache key generation.
        Note: the #fragment (if any) is intentionally dropped here — the server
        serves the same document regardless of the fragment, and all project-scoped
        cache keys should share one entry per page URL.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL string (fragment stripped)
        """
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Parse and reconstruct
        parsed = urlparse(url)

        # Remove trailing slash from path (unless it's just /)
        path = parsed.path
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]

        # Reconstruct URL (fragment intentionally omitted)
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized
