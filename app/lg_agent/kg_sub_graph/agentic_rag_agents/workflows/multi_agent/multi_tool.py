"""
多工具知识图谱查询工作流（子图）

本模块定义了 LangGraph 子图 —— 一个能够根据用户问题自动选择工具
（Text2Cypher / 预定义Cypher / GraphRAG）并执行知识图谱查询的 Agent 工作流。

工作流节点流程：
    START → guardrails（守卫校验）
         ├→ final_answer（校验不通过，直接结束）
         └→ planner（任务分解）
              └→ tool_selection（工具选择）
                   ├→ cypher_query（Text2Cypher 查询）
                   ├→ predefined_cypher（预定义 Cypher 查询）
                   └→ customer_tools（GraphRAG 查询）
                        └→ summarize（结果汇总）
                             └→ final_answer → END

作为外层 lg_builder 的 "create_research_plan" 子图，当用户查询被路由为
graphrag-query 类型时触发，负责从 Neo4j 知识图谱中检索答案。
"""

from typing import Any, Callable, Coroutine, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_neo4j import Neo4jGraph
from langgraph.constants import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from pydantic import BaseModel

# 导入输入输出状态定义
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.state import (
    InputState,
    OutputState,
    OverallState,
)
# 导入 Guardrails（业务范围守卫）逻辑 —— 过滤与电商业务无关的问题
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.guardrails.node import create_guardrails_node
# 导入任务分解（Planner）节点 —— 将复杂问题拆分为子任务
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.planner import create_planner_node
# 导入工具选择节点 —— 为每个子任务匹配合适的查询工具
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.tool_selection import create_tool_selection_node
# 导入 Text2Cypher 工具节点 —— 将自然语言转为 Cypher 查询语句
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.cypher_tools import create_cypher_query_node
# 导入 Cypher 示例检索器基类 —— 为 few-shot 提供参考样例
from app.lg_agent.kg_sub_graph.agentic_rag_agents.retrievers.cypher_examples.base import BaseCypherExampleRetriever
# 导入预定义 Cypher 工具节点 —— 执行预设的高频查询
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher import create_predefined_cypher_node
# 导入 GraphRAG 工具节点 —— 基于微软 GraphRAG 的知识检索
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.customer_tools import create_graphrag_query_node

# 错误处理节点 —— 工具选择失败时的兜底
from ...components.errors import create_error_tool_selection_node
# 最终答案生成节点 —— 整合结果并输出用户可读的回复
from ...components.final_answer import create_final_answer_node

# 汇总节点 —— 将多个工具的查询结果合并为统一上下文
from ...components.summarize import create_summarization_node

# 条件边定义 —— 控制工作流分支逻辑
from .edges import (
    guardrails_conditional_edge,          # 守卫校验结果决定继续 or 直接结束
    map_reduce_planner_to_tool_selection,  # 任务分解后路由到工具选择
)

from dataclasses import dataclass, field


# @dataclass(kw_only=True)： 强制要求数据类中的所有字段必须以关键字参数的形式提供。
# 即不能以位置参数的方式传递，提高代码可读性和参数安全性。
@dataclass(kw_only=True)
class AgentState(InputState):
    """知识图谱子图的内部状态，继承自 InputState。

    此状态在本子图内部流转，接收父图传入的 question，最终通过 answer
    将查询结果返回给父图。

    字段说明：
        - steps:    已完成的处理步骤列表，用于追踪工作流进度和调试
        - question: 从父图 (lg_builder) 传入的用户问题，作为子图的交互入口
        - answer:   子图查询完成后生成的最终答案，返回给父图
    """
    steps: list[str] = field(default_factory=list)
    question: str = field(default_factory=str)  # 与父图交互的输入参数
    answer: str = field(default_factory=str)    # 与父图交互的输出参数


def create_multi_tool_workflow(
    llm: BaseChatModel,
    graph: Neo4jGraph,
    tool_schemas: List[type[BaseModel]],
    predefined_cypher_dict: Dict[str, str],
    cypher_example_retriever: BaseCypherExampleRetriever,
    scope_description: Optional[str] = None,
    llm_cypher_validation: bool = True,
    max_attempts: int = 3,
    attempt_cypher_execution_on_final_attempt: bool = False,
    default_to_text2cypher: bool = True,
) -> CompiledStateGraph:
    """创建多工具知识图谱查询 Agent 工作流（LangGraph 子图）。

    此函数构建一个完整的知识图谱检索工作流，支持三种查询方式自动选择：
        1. Text2Cypher：   LLM 动态生成 Cypher 语句查询 Neo4j
        2. 预定义 Cypher：  执行预设的高频查询语句，结果更准确
        3. GraphRAG：       基于微软 GraphRAG 的知识增强检索

    工作流详细流程：
        ┌─────────────────────────────────────────────────────────┐
        │ 1. START → guardrails                                   │
        │    ├→ 问题在业务范围内 → 进入 planner                    │
        │    └→ 问题超出范围     → 直接 final_answer（返回兜底回复）│
        │                                                         │
        │ 2. planner → 将复杂问题拆解为多个子任务                   │
        │                                                         │
        │ 3. tool_selection → 为每个子任务选择最合适的工具           │
        │    ├→ cypher_query       (Text2Cypher 动态查询)          │
        │    ├→ predefined_cypher  (执行预定义 Cypher）             │
        │    └→ customer_tools     (GraphRAG 检索)                 │
        │                                                         │
        │ 4. summarize → 合并多工具返回结果为统一上下文              │
        │                                                         │
        │ 5. final_answer → 基于汇总结果生成用户可读的自然语言回复    │
        └─────────────────────────────────────────────────────────┘

    Parameters
    ----------
    llm : BaseChatModel
        用于推理、工具选择、Cypher 生成和验证的大语言模型实例。
    graph : Neo4jGraph
        Neo4j 图数据库连接包装器，用于执行 Cypher 查询。
    tool_schemas : List[type[BaseModel]]
        可用工具的 Pydantic 模式列表，每个工具对应一种查询能力。
        如 cypher_query、predefined_cypher、microsoft_graphrag_query。
    predefined_cypher_dict : Dict[str, str]
        预定义 Cypher 查询字典，key 为查询名称，value 为 Cypher 语句。
        用于高频固定查询场景，避免 LLM 动态生成的质量波动。
    cypher_example_retriever : BaseCypherExampleRetriever
        Cypher 示例检索器，根据用户问题检索相似的 Cypher 样例，
        以 few-shot 方式引导 LLM 生成更准确的 Cypher 语句。
    scope_description : Optional[str], optional
        电商业务经营范围描述，用于 Guardrails 节点判断用户问题
        是否与当前业务相关（如是否属于智能家居品类）。
    llm_cypher_validation : bool, optional
        是否启用 LLM 对生成的 Cypher 语句进行二次校验，默认 True。
        开启后会额外消耗 token，但能减少语法/语义错误。
    max_attempts : int, optional
        生成有效 Cypher 的最大尝试次数，默认 3 次。
        超过次数仍未生成有效语句则终止或使用兜底策略。
    attempt_cypher_execution_on_final_attempt : bool, optional
        ⚠️ 危险选项：最后一次尝试时，即使 Cypher 存在错误也强制执行。
        可能对数据库造成意外写入或性能影响，默认 False。
    default_to_text2cypher : bool, optional
        当 LLM 未返回工具调用时，是否默认降级为 Text2Cypher 查询，默认 True。

    Returns
    -------
    CompiledStateGraph
        编译后的 LangGraph 工作流图，可直接通过 .ainvoke(state) 执行。
    """
    # ================================================================
    # 创建工作流节点（每个节点是图中的一个独立处理单元）
    # ================================================================

    # 1. Guardrails（安全护栏）节点
    #    判断用户问题是否与当前电商业务范围相关。
    #    若超出范围（如问天气、政治），直接路由到 final_answer 返回兜底回复，
    #    避免对无关问题执行昂贵的 Neo4j 查询。
    guardrails = create_guardrails_node(
        llm=llm, graph=graph, scope_description=scope_description
    )

    # 2. Planner（任务分解）节点：复杂/多跳任务分解
    #    将用户的复杂问题拆解为多个可独立执行的子任务。
    #    例如"对比 A 品牌和 B 品牌的销量和好评率" → 拆为：
    #      - 子任务1：查询 A 品牌销量和好评率
    #      - 子任务2：查询 B 品牌销量和好评率
    #      - 子任务3：对比总结
    planner: Callable[[InputState], Coroutine[Any, Any, Dict[str, Any]]] = create_planner_node(llm=llm)

    # 3. Cypher Query（Text2Cypher）节点
    #    将自然语言子任务转为 Neo4j Cypher 查询语句并执行。
    #    LLM 基于 few-shot 样例生成 Cypher，带重试和校验机制。
    cypher_query = create_cypher_query_node()

    # 4. Predefined Cypher（预定义查询）节点
    #    执行预先写好的 Cypher 高频查询模板，结果稳定可靠。
    #    适合固定模式的统计查询（如 Top N 排行、销量统计等）。
    predefined_cypher = create_predefined_cypher_node(
        graph=graph, predefined_cypher_dict=predefined_cypher_dict
    )

    # 5. Customer Tools（GraphRAG）节点
    #    基于微软 GraphRAG 实现的知识增强检索，适合语义/概念级查询。
    #    不依赖 Cypher，而是通过图社区摘要 + 向量检索来回答。
    customer_tools = create_graphrag_query_node()

    # 6. Tool Selection（工具选择）节点
    #    读取 planner 拆解出的子任务列表，为每个子任务匹配最合适的工具。
    #    当 LLM 未明确工具调用时，可通过 default_to_text2cypher 降级为 Text2Cypher。
    tool_selection = create_tool_selection_node(
        llm=llm,
        tool_schemas=tool_schemas,
        default_to_text2cypher=default_to_text2cypher,
    )

    # 7. Summarize（结果汇总）节点
    #    将多个工具返回的结果合并为统一的文本上下文。
    #    消除不同工具输出格式的差异，为 final_answer 提供结构化材料。
    summarize = create_summarization_node(llm=llm)

    # 8. Final Answer（最终回答）节点
    #    基于 summarize 汇总后的上下文，生成面向用户的可读自然语言回复。
    #    同时将 answer 写入 OutputState，返回给父图。
    final_answer = create_final_answer_node()

    # ================================================================
    # 构建 LangGraph 状态图
    #   - OverallState: 图内部流转的完整状态
    #   - InputState:   外部（父图）传入的状态接口
    #   - OutputState:  对外暴露的输出字段
    # ================================================================
    main_graph_builder = StateGraph(OverallState, input=InputState, output=OutputState)

    # 注册所有节点到图中
    main_graph_builder.add_node(guardrails)
    main_graph_builder.add_node(planner)
    main_graph_builder.add_node("cypher_query", cypher_query)
    main_graph_builder.add_node(predefined_cypher)
    main_graph_builder.add_node("customer_tools", customer_tools)
    main_graph_builder.add_node(summarize)
    main_graph_builder.add_node(tool_selection)
    main_graph_builder.add_node(final_answer)

    # ================================================================
    # 添加边 —— 定义节点之间的流转关系
    # ================================================================

    # START → guardrails: 图启动后首先进入守卫校验节点
    main_graph_builder.add_edge(START, "guardrails")

    # guardrails → 条件分支:
    #   - 通过 → planner（继续后续查询流程）
    #   - 不通过 → final_answer（直接返回"超出业务范围"的兜底回复）
    main_graph_builder.add_conditional_edges(
        "guardrails",
        guardrails_conditional_edge,
    )

    # planner → tool_selection:
    #   将分解后的子任务列表传给工具选择节点，由 LLM 为每个子任务匹配工具。
    #   使用 map_reduce 策略：对每个子任务独立执行工具选择。
    main_graph_builder.add_conditional_edges(
        "planner",
        map_reduce_planner_to_tool_selection,  # type: ignore[arg-type, unused-ignore]
        ["tool_selection"],
    )

    # 工具节点 → summarize: 所有工具执行结果统一汇入汇总节点
    main_graph_builder.add_edge("cypher_query", "summarize")
    main_graph_builder.add_edge("predefined_cypher", "summarize")
    main_graph_builder.add_edge("customer_tools", "summarize")

    # summarize → final_answer → END: 汇总后生成最终回答，工作流结束
    main_graph_builder.add_edge("summarize", "final_answer")
    main_graph_builder.add_edge("final_answer", END)

    return main_graph_builder.compile()

