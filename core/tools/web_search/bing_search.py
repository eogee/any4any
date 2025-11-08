"""
Bing搜索引擎实现
源自于open-webSearch项目(https://github.com/Aas-ee/open-webSearch)，针对Python环境优化
"""
import asyncio
import time
import re
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

            # 创建会话 - 使用中文简体环境
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",  # 中文简体优先
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none"
            }

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
                trust_env=True  # 允许从环境变量读取代理
            )

        return self.session

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

            self.logger.info(f"开始搜索: '{clean_query}', 限制: {limit}")

            # 直接使用标准搜索，保持搜索引擎原始排序
            results = await self._standard_search(clean_query, limit)

            response_time = f"{time.time() - start_time:.1f}s"
            self.logger.info(f"搜索完成: 查询='{clean_query}', 结果数量={len(results)}, 耗时={response_time}")

            return results

        except Exception as e:
            if isinstance(e, (NetworkError, ParseError, TimeoutError, ProxyError)):
                raise

            # 包装其他异常
            raise NetworkError(f"搜索过程中发生错误: {str(e)}")

    async def _standard_search(self, clean_query: str, limit: int) -> List[SearchResult]:
        """标准搜索方法"""
        session = await self._get_session()
        all_results: List[SearchResult] = []
        page = 0

        seen_urls = set()  # 避免重复URL

        while len(all_results) < limit:
            offset = page * 10

            url = "https://cn.bing.com/search"
            params = {
                "q": clean_query,
                "first": offset + 1,
                "mkt": "zh-CN",
                "setlang": "zh-CN",
                "cc": "CN"
            }

            cookies = {
                "SRCHHPGUSR": "SRCHLANG=zh-CN",
                "_EDGE_V": "1",
                "MUID": "1234567890ABCDEF",
                "SRCHD": "AF=NOFORM",
                "SRCHUID": "V=2&GUID=1234567890ABCDEF&dmnchg=1",
                "SRCHS": "PC=VALB",
                "_EDGE_S": "SID=1234567890",
                "SRCHUSR": "DOB=20240101"
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

                    if len(all_results) < limit:
                        await asyncio.sleep(1)

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

            # 查找搜索结果容器 - 针对中文Bing搜索优化
            results_container = soup.find('ol', {'id': 'b_results'})
            if not results_container:
                # 尝试其他可能的选择器
                results_container = soup.find('div', {'id': 'b_content'})
                if results_container:
                    results_container = results_container.find('ol')
                else:
                    # 最后尝试使用class选择器
                    results_container = soup.find('ol', class_='b_results')

            if not results_container:
                # 如果都找不到，直接查找所有可能的li元素
                possible_items = soup.find_all('li', class_='b_algo')
            else:
                possible_items = results_container.find_all('li', class_='b_algo')

            # 如果还是没有找到结果，尝试更宽泛的选择器
            if not possible_items:
                possible_items = soup.find_all('li', class_=lambda x: x and 'b_algo' in x)

            if not possible_items:
                # 尝试查找包含链接的div元素（中文Bing可能使用不同结构）
                possible_items = soup.find_all('div', {'class': lambda x: x and 'b_result' in x if x else False})
                if not possible_items:
                    # 最后尝试查找所有包含h2或h3标签的元素
                    possible_items = [elem for elem in soup.find_all() if elem.find(['h2', 'h3']) and elem.find('a', href=True)]

            if not possible_items:
                # 添加调试信息
                self.logger.warning(f"HTML页面结构分析 - 找到的元素:")
                self.logger.warning(f"  - b_results: {soup.find('ol', {'id': 'b_results'}) is not None}")
                self.logger.warning(f"  - b_content: {soup.find('div', {'id': 'b_content'}) is not None}")
                self.logger.warning(f"  - b_algo class: {len(soup.find_all('li', class_='b_algo'))}")
                self.logger.warning(f"  - 包含h2/h3的元素: {len([elem for elem in soup.find_all() if elem.find(['h2', 'h3'])])}")
                raise ParseError("无法找到搜索结果容器或条目")

            # 解析每个搜索结果
            for item in possible_items:
                try:
                    # 提取标题和链接 - 使用更灵活的选择器
                    title_elem = item.find('h2')
                    if not title_elem:
                        # 尝试其他标题选择器
                        title_elem = item.find('a', href=True) or item.find('h3')

                    if not title_elem:
                        continue

                    # 提取链接
                    link_elem = title_elem if title_elem.name == 'a' else title_elem.find('a', href=True)
                    if not link_elem or not link_elem.get('href'):
                        continue

                    # 清理并获取标题
                    title = title_elem.get_text(strip=True) if title_elem.name != 'a' else link_elem.get_text(strip=True)
                    url = link_elem['href']

                    # 跳过无效链接
                    if not url.startswith('http'):
                        continue

                    # 提取描述 - 使用多个可能的选择器
                    description = ""
                    description_selectors = ['p', 'div.b_caption', 'div.b_snippet', 'span.b_caption']
                    for selector in description_selectors:
                        desc_elem = item.select_one(selector)
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)
                            break

                    # 提取来源 - 使用多个可能的选择器
                    source = ""
                    source_selectors = ['cite', 'span.b_attribution', 'div.b_attribution']
                    for selector in source_selectors:
                        source_elem = item.select_one(selector)
                        if source_elem:
                            source_text = source_elem.get_text(strip=True)
                            # 清理来源文本
                            source = re.sub(r'^[^a-zA-Z]*\s*', '', source_text)  # 移除前缀
                            source = re.sub(r'\s*[››].*$', '', source)  # 移除路径
                            source = re.sub(r'\s*-\s*.*$', '', source)   # 移除后缀
                            break

                    # 清理文本，移除特殊字符
                    title = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', title)
                    description = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', description)
                    source = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F\u3000]', '', source)

                    # 创建搜索结果对象
                    result = SearchResult(
                        title=title,
                        url=url,
                        description=description,
                        source=source,
                        engine="bing"
                    )

                    results.append(result)

                except Exception as e:
                    # 跳过解析失败的条目，继续处理其他结果
                    continue

            return results

        except Exception as e:
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