"""
Bing搜索引擎实现
源自于open-webSearch项目(https://github.com/Aas-ee/open-webSearch)，针对Python环境优化
"""
import asyncio
import time
import re
import random
from typing import List, Optional, Set
import aiohttp
from bs4 import BeautifulSoup

from .search_types import SearchResult
from .exceptions import NetworkError, ParseError, TimeoutError, ProxyError


class BingSearchEngine:
    """Bing搜索引擎"""

    def __init__(self, proxy_url: Optional[str] = None, timeout: int = 30):
        """
        初始化Bing搜索引擎

        Args:
            proxy_url: 代理URL，如 http://127.0.0.1:10809
            timeout: 请求超时时间（秒）
        """
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.session = None
        self._last_request_time = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)

            # 配置代理
            if self.proxy_url:
                try:
                    connector = aiohttp.TCPConnector(
                        limit=10,
                        limit_per_host=5,
                        use_dns_cache=True
                    )
                    # 代理配置
                    proxy = self.proxy_url
                except Exception as e:
                    raise ProxyError(f"代理配置错误: {str(e)}")
            else:
                proxy = None

            # 配置超时
            timeout = aiohttp.ClientTimeout(total=self.timeout)

            # 创建会话 - 使用随机User-Agent
            headers = self._get_headers()

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
                trust_env=True  # 允许从环境变量读取代理
            )

        return self.session

    def _get_headers(self) -> dict:
        """获取随机请求头"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": random.choice(["zh-CN,zh;q=0.9,en;q=0.8", "en-US,en;q=0.9", "en-US,en;q=0.8,zh-CN;q=0.5,zh;q=0.3"]),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        }

    async def _wait_before_request(self):
        """智能请求延迟"""
        now = time.time()
        time_since_last = now - self._last_request_time

        # 随机延迟：0.5-3秒
        min_delay = 0.5
        max_delay = 3.0
        required_delay = random.uniform(min_delay, max_delay)

        if time_since_last < required_delay:
            await asyncio.sleep(required_delay - time_since_last)

        self._last_request_time = time.time()

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            搜索结果列表

        Raises:
            NetworkError: 网络请求异常
            ParseError: HTML解析异常
            TimeoutError: 请求超时
            ProxyError: 代理异常
        """
        start_time = time.time()

        try:
            # 清理查询字符串
            clean_query = query.strip()
            if not clean_query:
                raise ValueError("搜索查询不能为空")

            # 智能请求延迟
            await self._wait_before_request()

            self.logger.info(f"开始搜索: '{clean_query}', 限制: {limit}")

            # 尝试多个Bing域名和搜索策略
            results = await self._search_with_fallback(clean_query, limit)

            response_time = f"{time.time() - start_time:.1f}s"
            self.logger.info(f"Search completed: Query='{clean_query}', Results count={len(results)}, Time taken={response_time}")

            return results

        except Exception as e:
            if isinstance(e, (NetworkError, ParseError, TimeoutError, ProxyError)):
                raise

            # 包装其他异常
            raise NetworkError(f"搜索过程中发生错误: {str(e)}")

    async def _search_with_fallback(self, clean_query: str, limit: int) -> List[SearchResult]:
        """使用故障转移机制搜索"""
        # 尝试多个Bing域名和配置
        search_strategies = [
            {"url": "https://www.bing.com/search", "market": "zh-CN", "lang": "zh-CN", "cc": "CN"},
            {"url": "https://cn.bing.com/search", "market": "zh-CN", "lang": "zh-CN", "cc": "CN"},
            {"url": "https://www.bing.com/search", "market": "en-US", "lang": "en", "cc": "US"},
            {"url": "https://www.bing.com/search", "market": "en-GB", "lang": "en", "cc": "GB"}
        ]

        for i, strategy in enumerate(search_strategies):
            try:
                self.logger.info(f"尝试搜索策略 {i+1}: {strategy['url']}")
                results = await self._standard_search_with_strategy(clean_query, limit, strategy)
                if results:
                    return results
            except Exception as e:
                self.logger.warning(f"搜索策略 {i+1} 失败: {e}")
                continue

        # 所有策略都失败，尝试标准搜索作为最后的努力
        try:
            return await self._standard_search(clean_query, limit)
        except Exception as e:
            self.logger.error(f"所有搜索策略均失败: {e}")
            raise

    async def _standard_search_with_strategy(self, clean_query: str, limit: int, strategy: dict) -> List[SearchResult]:
        """使用指定策略的标准搜索方法"""
        session = await self._get_session()
        all_results: List[SearchResult] = []
        page = 0
        max_pages = 3  # 限制页数，防止过度请求

        seen_urls = set()  # 避免重复URL

        while len(all_results) < limit and page < max_pages:
            offset = page * 10

            url = strategy["url"]
            params = {
                "q": clean_query,
                "first": offset + 1,
                "mkt": strategy["market"],
                "setlang": strategy["lang"],
                "cc": strategy["cc"]
            }

            cookies = {
                "SRCHHPGUSR": f"SRCHLANG={strategy['lang']}",
                "_EDGE_V": "1",
                "MUID": "1234567890ABCDEF",
                "SRCHD": "AF=NOFORM",
                "SRCHUID": "V=2&GUID=1234567890ABCDEF&dmnchg=1",
                "SRCHS": "PC=VALB",
                "_EDGE_S": "SID=1234567890",
                "SRCHUSR": "DOB=19900101"
            }

            try:
                async with session.get(url, params=params, cookies=cookies) as response:
                    if response.status != 200:
                        raise NetworkError(f"HTTP请求失败: {response.status}")

                    html = await response.text()
                    page_results = await self._parse_search_results(html)

                    if not page_results:
                        break

                    # 添加结果时进行基本的URL去重
                    new_results = []
                    for result in page_results:
                        if result.url not in seen_urls:
                            seen_urls.add(result.url)
                            new_results.append(result)
                        if len(all_results) + len(new_results) >= limit:
                            break

                    if not new_results:
                        break

                    all_results.extend(new_results)
                    page += 1

                    # 智能延迟
                    if len(all_results) < limit:
                        await self._wait_before_request()

            except asyncio.TimeoutError:
                raise TimeoutError(f"请求超时: {self.timeout}秒")
            except aiohttp.ClientError as e:
                raise NetworkError(f"网络请求错误: {str(e)}")

        return all_results[:limit]

    
    async def _search_with_site_restriction(self, query: str, limit: int) -> List[SearchResult]:
        """使用站点限制搜索"""
        session = await self._get_session()

        # 直接使用原始查询，不进行站点限制
        search_query = query

        url = "https://cn.bing.com/search"
        params = {
            "q": search_query,
            "first": 1,
            "mkt": "zh-CN",
            "setlang": "zh-CN",
            "cc": "CN"
        }

        cookies = {
            "SRCHHPGUSR": "SRCHLANG=zh-CN",
            "_EDGE_V": "1",
            "MUID": "1234567890ABCDEF",
        }

        try:
            async with session.get(url, params=params, cookies=cookies) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                return await self._parse_search_results(html)

        except Exception as e:
            self.logger.warning(f"站点限制搜索失败: {e}")
            return []

    async def _search_with_different_markets(self, query: str, limit: int) -> List[SearchResult]:
        """使用不同市场设置搜索"""
        session = await self._get_session()

        # 尝试不同的市场设置（优先中文地区）
        markets = ["zh-CN", "zh-HK", "zh-TW", "en-SG", "en-AU"]

        for market in markets[:2]:  # 只尝试前两个
            params = {
                "q": query,
                "first": 1,
                "mkt": market,
                "setlang": "zh-CN",
                "cc": market.split('-')[1].upper()
            }

            cookies = {
                "SRCHHPGUSR": f"SRCHLANG=zh-CN&mkt={market}",
                "_EDGE_V": "1",
                "MUID": "1234567890ABCDEF",
            }

            try:
                async with session.get("https://cn.bing.com/search", params=params, cookies=cookies) as response:
                    if response.status != 200:
                        continue

                    html = await response.text()
                    results = await self._parse_search_results(html)
                    if results:
                        return results

            except Exception as e:
                self.logger.warning(f"市场 {market} 搜索失败: {e}")
                continue

        return []

    async def _search_with_query_modifiers(self, query: str, limit: int) -> List[SearchResult]:
        """使用查询修饰符搜索"""
        session = await self._get_session()

        # 添加查询修饰符来获得不同类型的结果
        modifiers = [
            f"{query} tutorial",
            f"{query} documentation",
            f"{query} guide",
            f"{query} official"
        ]

        for modifier in modifiers[:2]:  # 只尝试前两个
            params = {
                "q": modifier,
                "first": 1,
                "mkt": "zh-CN",
                "setlang": "zh-CN",
                "cc": "CN"
            }

            cookies = {
                "SRCHHPGUSR": "SRCHLANG=zh-CN",
                "_EDGE_V": "1",
                "MUID": "1234567890ABCDEF",
            }

            try:
                async with session.get("https://cn.bing.com/search", params=params, cookies=cookies) as response:
                    if response.status != 200:
                        continue

                    html = await response.text()
                    results = await self._parse_search_results(html)
                    if results:
                        return results

            except Exception as e:
                self.logger.warning(f"修饰符搜索 {modifier} 失败: {e}")
                continue

        return []

    async def _parse_search_results(self, html: str) -> List[SearchResult]:
        """
        解析搜索结果HTML

        Args:
            html: 搜索结果页面HTML

        Returns:
            解析出的搜索结果列表

        Raises:
            ParseError: HTML解析失败
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results: List[SearchResult] = []

            # 多重选择器策略，增强容错能力
            selectors = [
                'ol#b_results > li.b_algo',           # 标准Bing选择器
                'div.b_content ol li.b_algo',         # 备用容器选择器
                'ol.b_results li.b_algo',             # class选择器
                'li[class*="b_algo"]',               # 包含b_algo的类名
                'div.b_result',                       # 结果div
                'ol.b_results li',                    # 简化选择器
                '[class*="b_algo"]'                  # 最宽泛选择器
            ]

            possible_items = []
            for selector in selectors:
                try:
                    items = soup.select(selector)
                    if items:
                        possible_items = items
                        self.logger.debug(f"使用选择器 '{selector}' 找到 {len(items)} 个结果")
                        break
                except Exception as e:
                    self.logger.debug(f"选择器 '{selector}' 失败: {e}")
                    continue

            # 最后的容错策略：查找包含链接的任何元素
            if not possible_items:
                possible_items = [elem for elem in soup.find_all()
                                if elem.find('a', href=True) and
                                (elem.find('h2') or elem.find('h3') or elem.find('cite'))]

            if not possible_items:
                # 检查是否被重定向到验证页面
                if "captcha" in html.lower() or "verify" in html.lower():
                    raise NetworkError("遇到反爬虫验证页面")

                self.logger.warning("未找到任何搜索结果，可能页面结构已变化")
                return results

            # 解析每个搜索结果
            for item in possible_items:
                try:
                    # 多重标题选择器策略
                    title_selectors = ['h2', 'h3', 'a[href]', '.b_title']
                    title = None
                    link = None

                    for selector in title_selectors:
                        try:
                            if selector == 'a[href]':
                                link_elem = item.select_one(selector)
                                if link_elem:
                                    title = link_elem.get_text(strip=True)
                                    link = link_elem.get('href')
                                    break
                            else:
                                title_elem = item.select_one(selector)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    # 查找关联的链接
                                    link_elem = title_elem.find('a') or item.select_one('a[href]')
                                    if link_elem:
                                        link = link_elem.get('href')
                                    break
                        except Exception:
                            continue

                    if not title or not link:
                        continue

                    # 验证和清理链接
                    if not link.startswith('http') or link.startswith('#'):
                        continue

                    # 清理标题
                    title = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', title)
                    if len(title) < 3 or len(title) > 200:
                        continue

                    # 多重描述选择器
                    description = ""
                    description_selectors = [
                        'p', 'div.b_caption', 'div.b_snippet', 'span.b_caption',
                        '.b_caption p', '.b_snippet', '.b_description'
                    ]
                    for selector in description_selectors:
                        try:
                            desc_elem = item.select_one(selector)
                            if desc_elem:
                                desc_text = desc_elem.get_text(strip=True)
                                if desc_text and len(desc_text) > 20:
                                    description = desc_text
                                    break
                        except Exception:
                            continue

                    # 多重来源选择器
                    source = ""
                    source_selectors = [
                        'cite', 'span.b_attribution', 'div.b_attribution',
                        '.b_attribution', '.b_source', 'cite[role="text"]'
                    ]
                    for selector in source_selectors:
                        try:
                            source_elem = item.select_one(selector)
                            if source_elem:
                                source_text = source_elem.get_text(strip=True)
                                if source_text and len(source_text) > 2:
                                    # 清理来源文本
                                    source = re.sub(r'^[^a-zA-Z0-9]*\s*', '', source_text)
                                    source = re.sub(r'\s*[››].*$', '', source)
                                    source = re.sub(r'\s*-\s*.*$', '', source)
                                    source = re.sub(r'\s*\.\s*.*$', '', source)
                                    break
                        except Exception:
                            continue

                    # 清理描述文本
                    description = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', description)

                    # 创建搜索结果对象
                    result = SearchResult(
                        title=title,
                        url=link,
                        description=description,
                        source=source,
                        engine="bing"
                    )

                    results.append(result)

                except Exception as e:
                    # 跳过解析失败的条目，继续处理其他结果
                    self.logger.debug(f"解析单个结果失败: {e}")
                    continue

            self.logger.info(f"成功解析 {len(results)} 个搜索结果")
            return results

        except Exception as e:
            self.logger.error(f"HTML解析失败: {str(e)}")
            raise ParseError(f"HTML解析失败: {str(e)}")

    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 创建logger
import logging
BingSearchEngine.logger = logging.getLogger(__name__)


class DuckDuckGoSearchEngine:
    """DuckDuckGo搜索引擎"""

    def __init__(self, proxy_url: Optional[str] = None, timeout: int = 30):
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.session = None
        self._last_request_time = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = self._get_headers()

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
                trust_env=True
            )
        return self.session

    def _get_headers(self) -> dict:
        """获取随机请求头"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    async def _wait_before_request(self):
        """智能请求延迟"""
        now = time.time()
        time_since_last = now - self._last_request_time

        # 随机延迟：0.5-3秒
        min_delay = 0.5
        max_delay = 3.0
        required_delay = random.uniform(min_delay, max_delay)

        if time_since_last < required_delay:
            await asyncio.sleep(required_delay - time_since_last)

        self._last_request_time = time.time()

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """执行DuckDuckGo搜索"""
        await self._wait_before_request()
        session = await self._get_session()

        try:
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query.strip()}

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise NetworkError(f"HTTP请求失败: {response.status}")

                html = await response.text()
                return await self._parse_search_results(html)

        except Exception as e:
            raise NetworkError(f"DuckDuckGo搜索失败: {e}")

    async def _parse_search_results(self, html: str) -> List[SearchResult]:
        """解析DuckDuckGo搜索结果"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results: List[SearchResult] = []

            # DuckDuckGo特定的选择器
            result_items = soup.select('div.results_links_deep')

            if not result_items:
                # 尝试其他选择器
                result_items = soup.select('.result')
                if not result_items:
                    result_items = soup.select('article.result')

            for item in result_items:
                try:
                    title_elem = item.select_one('a.result__a, h2 a, .result__title a')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href')

                    if not title or not link:
                        continue

                    # DuckDuckGo链接需要解码
                    if 'duckduckgo.com/l/?uddg=' in link:
                        import urllib.parse
                        link = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])

                    if not link.startswith('http'):
                        continue

                    # 提取描述
                    desc_elem = item.select_one('.result__snippet, .result__description, p')
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    # 清理文本
                    title = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', title)
                    description = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', description)

                    results.append(SearchResult(
                        title=title,
                        url=link,
                        description=description,
                        source="",
                        engine="duckduckgo"
                    ))

                except Exception as e:
                    continue

            return results

        except Exception as e:
            raise ParseError(f"DuckDuckGo HTML解析失败: {str(e)}")

    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 创建logger
DuckDuckGoSearchEngine.logger = logging.getLogger(__name__)