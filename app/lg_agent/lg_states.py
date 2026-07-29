"""
Agent 状态定义模块

本模块定义了 LangGraph Agent 工作流中使用的所有状态数据结构。
这些状态对象在图的各个节点之间流转，承载用户输入、中间处理结果和最终输出。

包含的核心数据模型：
    - Router: 用户查询的路由分类，决定后续处理分支
    - GradeHallucinations: 幻觉检测评分，评估回答的事实依据
    - InputState: Agent 的输入状态，管理多轮对话消息
    - AgentState: Agent 的完整工作流状态，继承自 InputState
"""

from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict, List
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class Router(TypedDict):
    """路由分类：用于对用户查询进行分类，决定后续走哪个处理分支。

    通过 LLM 分析用户意图后填充，随后 LangGraph 条件边根据 type 字段
    将流程路由到对应的处理节点（如通用问答、图像生成、文件处理等）。
    """
    # 路由的分类逻辑说明（由 LLM 生成的推理过程）
    logic: str
    # 查询类型，决定后续的路由目标节点
    #   - "general-query":      通用对话 / 知识问答
    #   - "additional-query":   对上一轮回答的追问或补充
    #   - "graphrag-query":     需要从知识图谱中检索的查询
    #   - "image-query":        与图片生成或图片理解相关的查询
    #   - "file-query":         与文件处理（上传/分析/下载）相关的查询
    type: Literal["general-query", "additional-query", "graphrag-query", "image-query", "file-query"]
    # 经过路由节点处理后的改写/精炼问题
    # question: str = field(default_factory=str)  # TypedDict 不支持默认值，question 仅做类型声明
    question: str


class GradeHallucinations(BaseModel):
    """幻觉检测评估：对 Agent 最终生成回答的事实依据进行二分类评分。

    用于在回答生成后，由独立的校验节点（如 LLM 评审）判断回答内容
    是否基于检索到的文档或可靠事实，而非模型自己编造。
    采用 Pydantic BaseModel 以便 LLM 结构化输出时直接填充。
    """
    # 二分类评分：'1' 表示回答有事实依据，'0' 表示存在幻觉（偏离事实）
    binary_score: str = Field(
        description="Answer is grounded in the facts, '1' or '0'"
    )


# @dataclass(kw_only=True)： 强制要求数据类中的所有字段必须以关键字参数的形式提供。
# 即不能以位置参数的方式传递，必须使用关键字参数，提高代码可读性和安全性。
@dataclass(kw_only=True)
class InputState:
    """Agent 的输入状态，承载多轮对话中的消息历史。

    这是 LangGraph 工作流图的入口状态。图在运行时接收此类实例，
    其中的 messages 字段通过 add_messages 合并策略来累积对话。

    add_messages 合并策略说明：
        - 默认以"追加"模式运行：新消息会追加到已有消息列表末尾。
        - 如果新消息的 ID 与已有消息 ID 相同，则覆盖（替换）旧消息，
          这确保了消息可以被更新而不仅仅是追加。

    典型的消息流转模式（ReAct / Tool-calling 模式）：
        1. HumanMessage              - 用户输入
        2. AIMessage（含 .tool_calls） - Agent 选择工具准备调用
        3. ToolMessage(s)            - 工具执行后返回结果
           （... 根据需要重复步骤 2 和 3 ...）
        4. AIMessage（无 .tool_calls） - Agent 生成最终自然语言回答
        5. HumanMessage              - 用户开始下一轮对话
           （... 重复步骤 2-5 ...）
    """
    # 对话消息列表，使用 LangGraph 的 add_messages 作为 reducer
    # 类型：带注解的 AnyMessage 列表，确保消息的有序累积
    messages: Annotated[list[AnyMessage], add_messages]


# @dataclass(kw_only=True)： 强制要求数据类中的所有字段必须以关键字参数的形式提供。
@dataclass(kw_only=True)
class AgentState(InputState):
    """Agent 图工作流的完整状态，继承自 InputState。

    在整个 LangGraph 工作流图中流转，各节点读取并更新相关字段。
    当图执行完毕时，answer 字段包含最终返回给用户的回答。

    字段说明：
        - messages:       (继承自 InputState) 多轮对话历史
        - router:         当前路由信息，由路由节点填充
        - steps:          已完成的处理阶段列表（如 ["retrieve", "grade", "generate"]）
        - question:       用户当前轮次的原始问题
        - answer:         最终生成的回答文本（也可能在中间步骤中暂存）
        - hallucination:  幻觉检测结果，由校验节点评估后写入
    """
    # 路由分类信息，默认初始化为 general-query 类型
    router: Router = field(default_factory=lambda: Router(type="general-query", logic=""))
    # 已走过的处理步骤，用于追踪工作流进度和调试
    steps: list[str] = field(default_factory=list)
    # 用户当前轮次的原始问题文本
    question: str = field(default_factory=str)
    # 最终生成的回答内容，在工作流的生成节点中填充
    answer: str = field(default_factory=str)
    # 幻觉检测评估结果，默认初始化为 '0'（待评估状态）
    hallucination: GradeHallucinations = field(default_factory=lambda: GradeHallucinations(binary_score="0"))
