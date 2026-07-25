"""
SerpAPI 互联网搜索工具。

通过 SerpAPI 调用 Google 搜索引擎，获取实时网页搜索结果，
返回结构化的标题、链接和摘要信息，供 SearchService 使用。
"""

import requests
from typing import List, Dict
from app.core.config import settings

class SearchTool:
    """SerpAPI 搜索工具"""

    def __init__(self):
        self.api_key = settings.SERPAPI_KEY
        if not self.api_key:
            raise ValueError("未设置SERPAPI_KEY环境变量")

    def search(self, query: str, num_results: int = 2) -> List[Dict]:
        """执行 Google 搜索并返回结构化结果列表"""
        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "hl": "zh-CN",
                "gl": "cn"
            }

            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=15
            )
            response.raise_for_status()

            return self._parse_results(response.json())

        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return []

    def _parse_results(self, data: dict) -> List[Dict]:
        """解析 SerpAPI 返回的原始 JSON 数据，提取标题、链接和摘要"""
        results = []

        if "organic_results" in data:
            for item in data["organic_results"]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

        return results[:3]  # 只返回前3条结果