"""
SerpAPI 联网搜索独立测试脚本。

验证 SerpAPI / Google 搜索是否能正常返回结构化结果，
解析有机搜索结果和知识图谱信息，不依赖后端服务。
"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")
SEARCH_ENGINE = "google"


def serpapi_search(query: str, num_results: int = 5) -> list[dict]:
    """执行 SerpAPI 搜索并返回结构化结果列表"""
    if not API_KEY:
        raise ValueError("未设置SERPAPI_KEY环境变量。请在.env文件中设置您的API密钥。")

    try:
        params = {
            "engine": SEARCH_ENGINE,
            "q": query,
            "api_key": API_KEY,
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

        search_data = response.json()
        return _parse_serpapi_results(search_data)

    except Exception as e:
        print(f"搜索失败: {str(e)}")
        return []

def _parse_serpapi_results(data: dict) -> list[dict]:
    """解析 SerpAPI 返回的原始数据，提取有机结果和知识图谱信息"""
    results = []

    # 提取有机搜索结果（非广告）
    if "organic_results" in data:
        for item in data["organic_results"]:
            result = {
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
                "source": "web",
                "timestamp": item.get("date")
            }
            results.append(result)

    # 提取知识图谱信息（直接答案），置顶显示
    if "knowledge_graph" in data:
        kg = data["knowledge_graph"]
        results.insert(0, {
            "title": kg.get("title"),
            "url": kg.get("source")["link"] if "source" in kg else "",
            "snippet": kg.get("description"),
            "source": "knowledge_graph"
        })

    return results

if __name__ == "__main__":
    test_query = "deepseek-R1模型使用了什么新的训练方法？"
    search_results = serpapi_search(test_query)

    print(f"搜索词: {test_query}")
    for idx, result in enumerate(search_results, 1):
        print(f"\n结果 {idx}:")
        print(f"标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"摘要: {result['snippet']}")