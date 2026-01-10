"""
LangGraph Multi-Agent Workflow

This module defines a simple multi-agent system using LangGraph:
- Research Agent: Analyzes the user query and gathers relevant information
- Writer Agent: Synthesizes the research into a coherent response

The workflow demonstrates how to:
1. Define agent state
2. Create agent nodes
3. Build a graph with conditional routing
4. Execute the workflow
"""
from __future__ import annotations

from typing import Annotated, TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.core.config import get_settings


# =============================================================================
# State Definition
# =============================================================================


class AgentState(TypedDict):
    """
    State that flows through the agent graph.

    Attributes:
        messages: Conversation history (automatically appended)
        user_query: The original user question
        research: Research findings from the research agent
        final_response: The final synthesized response
        agent_steps: Log of which agents ran and what they did
    """

    messages: Annotated[list, add_messages]
    user_query: str
    research: str
    final_response: str
    agent_steps: list[dict]


# =============================================================================
# Agent Nodes
# =============================================================================


def get_llm():
    """Get configured LLM instance."""
    settings = get_settings()
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",  # Fast and cost-effective Claude Haiku 4.5
        api_key=settings.anthropic_api_key,
        temperature=0.7,
    )


def research_agent(state: AgentState) -> AgentState:
    """
    Research Agent: Analyzes the query and provides structured insights.

    This agent acts as a researcher, breaking down the query and
    identifying key aspects that need to be addressed.
    """
    llm = get_llm()

    system_prompt = """You are a Research Agent. Your job is to analyze the user's
question and provide structured research notes that will help another agent
write a comprehensive response.

Your research should:
1. Identify the key aspects of the question
2. Note any important context or considerations
3. Outline the main points that should be covered in a response

Keep your research concise but thorough. Format as bullet points."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research this query: {state['user_query']}"),
    ]

    response = llm.invoke(messages)

    return {
        "research": response.content,
        "agent_steps": state.get("agent_steps", [])
        + [{"agent": "research", "output": response.content}],
    }


def writer_agent(state: AgentState) -> AgentState:
    """
    Writer Agent: Synthesizes research into a polished response.

    This agent takes the research from the Research Agent and
    crafts a coherent, helpful response for the user.
    """
    llm = get_llm()

    system_prompt = """You are a Writer Agent. Your job is to take research notes
and synthesize them into a clear, helpful response for the user.

Guidelines:
- Write in a conversational but informative tone
- Structure your response logically
- Be concise but thorough
- Address all key points from the research"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"""Based on this research:

{state['research']}

Write a response to the user's original question: {state['user_query']}"""
        ),
    ]

    response = llm.invoke(messages)

    return {
        "final_response": response.content,
        "messages": [AIMessage(content=response.content)],
        "agent_steps": state.get("agent_steps", [])
        + [{"agent": "writer", "output": response.content}],
    }


# =============================================================================
# Graph Construction
# =============================================================================


def build_agent_graph() -> StateGraph:
    """
    Build the multi-agent workflow graph.

    Flow:
    1. research_agent: Analyzes the query
    2. writer_agent: Synthesizes the response
    3. END: Workflow complete

    This is a simple sequential flow, but LangGraph supports
    conditional branching, loops, and more complex patterns.
    """
    # Initialize the graph with our state type
    workflow = StateGraph(AgentState)

    # Add nodes (agents)
    # Note: Node names must differ from state keys to avoid conflicts
    workflow.add_node("research_node", research_agent)
    workflow.add_node("writer_node", writer_agent)

    # Define the flow
    workflow.set_entry_point("research_node")
    workflow.add_edge("research_node", "writer_node")
    workflow.add_edge("writer_node", END)

    return workflow


# Create compiled graph (singleton)
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_agent_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


# =============================================================================
# Main Entry Point
# =============================================================================


async def run_agent_workflow(
    user_query: str, conversation_history: list[dict] | None = None
) -> dict:
    """
    Run the multi-agent workflow for a user query.

    Args:
        user_query: The user's question or message
        conversation_history: Optional list of previous messages

    Returns:
        dict with:
            - response: The final response text
            - agent_steps: List of agent actions taken
    """
    # Initialize state
    initial_state: AgentState = {
        "messages": conversation_history or [],
        "user_query": user_query,
        "research": "",
        "final_response": "",
        "agent_steps": [],
    }

    # Run the graph
    graph = get_compiled_graph()
    final_state = await graph.ainvoke(initial_state)

    return {
        "response": final_state["final_response"],
        "agent_steps": final_state["agent_steps"],
    }
