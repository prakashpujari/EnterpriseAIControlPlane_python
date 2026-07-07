"""
LangGraph workflow orchestration for Enterprise AI Customer Support Assistant.
Defines the agentic workflow: Planner → Workers → Critic → Memory.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import logging
import uuid

from app.models.database import ChatRequest, ChatResponse
from app.agents.planner import get_planner, PlannerResult, QueryType
from app.agents.faq_agent import get_faq_agent, FAQResult
from app.agents.rag_agent import get_rag_agent, RAGResult
from app.agents.summarizer_agent import get_summarizer_agent, SummaryResult
from app.agents.reasoning_agent import get_reasoning_agent, ReasoningResult, EscalationLevel
from app.agents.critic_agent import get_critic_agent, CriticResult
from app.agents.memory_agent import get_memory_agent, MemoryUpdateResult
from app.memory.stm import STMManager
from app.memory.compression import ContextCompressor
from app.gateway.audit import get_audit_logger, AuditAction
from app.config.llm_providers import model_router, get_claude_client
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the agentic workflow."""

    # Input
    query: str
    role: str
    user_id: Optional[str]
    session_id: Optional[str]
    context: Optional[Dict[str, Any]]

    # Planner output
    query_type: QueryType
    planner_confidence: float
    selected_tools: List[str]
    complexity: str
    recommended_model_tier: str

    # Worker outputs
    faq_result: Optional[FAQResult]
    rag_result: Optional[RAGResult]
    summary_result: Optional[SummaryResult]
    reasoning_result: Optional[ReasoningResult]

    # Critic output
    critic_result: Optional[CriticResult]

    # Memory output
    memory_result: Optional[MemoryUpdateResult]

    # Final output
    response: str
    sources: List[Dict[str, Any]]
    is_valid: bool
    latency_ms: int
    tokens_input: int
    tokens_output: int
    model_used: str

    # Error handling
    error: Optional[str]


class ChatWorkflow:
    """
    Orchestrates the chat workflow using LangGraph.
    """

    def __init__(self, db_session=None):
        self.stm_manager = STMManager(db_session) if db_session else None
        self.planner = get_planner()
        self.faq_agent = get_faq_agent()
        self.rag_agent = get_rag_agent()
        self.summarizer_agent = get_summarizer_agent()
        self.reasoning_agent = get_reasoning_agent()
        self.critic_agent = get_critic_agent()
        self.memory_agent = get_memory_agent()
        self.compressor = ContextCompressor()
        self.client = get_claude_client()
        self.audit_logger = get_audit_logger(db_session)

    async def process_query(
        self,
        request: ChatRequest,
        user_id: str = None,
    ) -> ChatResponse:
        """
        Process a chat query through the workflow.

        Args:
            request: Chat request
            user_id: Optional user ID (from authenticated user)

        Returns:
            ChatResponse
        """
        import time

        start_time = time.time()

        # Initialize state
        state: AgentState = {
            "query": request.query,
            "role": request.role,
            "user_id": user_id or request.session_id,
            "session_id": request.session_id,
            "context": request.context,
            "query_type": QueryType.UNKNOWN,
            "planner_confidence": 0.0,
            "selected_tools": [],
            "complexity": "medium",
            "recommended_model_tier": "medium",
            "faq_result": None,
            "rag_result": None,
            "summary_result": None,
            "reasoning_result": None,
            "critic_result": None,
            "memory_result": None,
            "response": "",
            "sources": [],
            "is_valid": True,
            "latency_ms": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "model_used": "",
            "error": None,
        }

        # Log audit start
        if self.audit_logger:
            await self.audit_logger.log_action(
                action=AuditAction.CHAT_QUERY,
                user_id=user_id or request.session_id,
                role=request.role,
                request_data={"query": request.query[:100]},
            )

        try:
            # Execute workflow
            result = await self._execute_workflow(state)

            latency_ms = int((time.time() - start_time) * 1000)

            # Log audit end
            if self.audit_logger:
                await self.audit_logger.log_action(
                    action=AuditAction.CHAT_RESPONSE,
                    user_id=user_id or request.session_id,
                    role=request.role,
                    model_used=model_router.route_query(
                        result["query_type"].value,
                        request.role,
                        result["complexity"],
                    ),
                    response_data={"response": result["response"][:100]},
                    latency_ms=latency_ms,
                    outcome="success" if result["is_valid"] else "blocked",
                )

            return ChatResponse(
                response=result["response"],
                session_id=result["session_id"],
                sources=result["sources"],
                model_used=result["model_used"],
                tokens_input=result["tokens_input"],
                tokens_output=result["tokens_output"],
                latency_ms=latency_ms,
                is_valid=result["is_valid"],
                suggestions=[],
            )

        except Exception as e:
            logger.error(f"Workflow error: {e}")

            if self.audit_logger:
                await self.audit_logger.log_action(
                    action=AuditAction.CHAT_RESPONSE,
                    user_id=user_id or request.session_id,
                    role=request.role,
                    outcome="failure",
                    response_data={"error": str(e)},
                )

            return ChatResponse(
                response="I apologize, but an error occurred while processing your request. Please try again.",
                session_id=request.session_id or str(uuid.uuid4()),
                sources=[],
                model_used=settings.SMALL_MODEL,
                tokens_input=0,
                tokens_output=0,
                latency_ms=int((time.time() - start_time) * 1000),
                is_valid=False,
                suggestions=["Retry request", "Contact support"],
            )

    async def _execute_workflow(self, state: AgentState) -> AgentState:
        """
        Execute the agentic workflow.

        Args:
            state: Initial state

        Returns:
            Final state
        """
        # Step 1: Planner
        planner_result = await self.planner.classify_query(
            query=state["query"],
            context=state.get("context"),
            role=state["role"],
        )

        state["query_type"] = planner_result.query_type
        state["planner_confidence"] = planner_result.confidence
        state["selected_tools"] = planner_result.selected_tools
        state["complexity"] = planner_result.complexity
        state["recommended_model_tier"] = planner_result.recommended_model_tier
        state["model_used"] = model_router.get_model_config(
            planner_result.recommended_model_tier
        )["model"]

        # Step 2: Route to appropriate worker
        if state["query_type"] == QueryType.FAQ:
            result = await self.faq_agent.answer_question(
                query=state["query"],
                role=state["role"],
                context=state.get("context"),
            )
            state["faq_result"] = result
            state["response"] = result.answer
            state["sources"] = result.sources
            state["tokens_input"] = result.tokens_input
            state["tokens_output"] = result.tokens_output

        elif state["query_type"] == QueryType.RAG:
            result = await self.rag_agent.answer_question(
                query=state["query"],
                role=state["role"],
                context=state.get("context"),
            )
            state["rag_result"] = result
            state["response"] = result.answer
            state["sources"] = result.citations
            state["tokens_input"] = result.tokens_input
            state["tokens_output"] = result.tokens_output

        elif state["query_type"] == QueryType.SUMMARIZE:
            result = await self.summarizer_agent.summarize(
                text=state["query"],
            )
            state["summary_result"] = result
            state["response"] = result.summary
            state["tokens_input"] = result.tokens_input
            state["tokens_output"] = result.tokens_output

        elif state["query_type"] == QueryType.REASON:
            result = await self.reasoning_agent.analyze(
                query=state["query"],
                role=state["role"],
                context=state.get("context"),
            )
            state["reasoning_result"] = result
            state["response"] = result.answer
            state["sources"] = []
            state["tokens_input"] = result.tokens_input
            state["tokens_output"] = result.tokens_output

        else:
            # Fallback to FAQ
            result = await self.faq_agent.answer_question(
                query=state["query"],
                role=state["role"],
            )
            state["faq_result"] = result
            state["response"] = result.answer
            state["tokens_input"] = result.tokens_input
            state["tokens_output"] = result.tokens_output

        # Step 2b: Guarantee a usable (non-empty) response.
        # Some worker agents (notably the FAQ agent) return an empty string
        # for queries they don't recognize, which would otherwise surface to
        # the user as a blank message. Fall back to a direct LLM answer.
        if not state["response"] or not state["response"].strip():
            logger.info("Worker returned empty response; using direct LLM fallback")
            state["response"] = await self._generate_fallback_response(
                query=state["query"],
                role=state["role"],
                context=state.get("context"),
            )
            state["model_used"] = model_router.get_model_config("small")["model"]

        # Step 3: Critic validation
        critic_result = await self.critic_agent.validate(
            response=state["response"],
            query=state["query"],
            sources=state.get("sources"),
            role=state["role"],
            context=state.get("context"),
        )
        state["critic_result"] = critic_result
        state["is_valid"] = critic_result.is_valid

        # Step 4: Memory update
        if self.stm_manager and state.get("user_id"):
            turns = [{"role": "user", "content": state["query"]}]
            if state["response"]:
                turns.append({"role": "assistant", "content": state["response"]})

            memory_result = await self.memory_agent.update_memory(
                session_id=state.get("session_id", ""),
                user_id=state["user_id"],
                conversation_turns=turns,
                role=state["role"],
            )
            state["memory_result"] = memory_result

        return state

    async def _generate_fallback_response(
        self,
        query: str,
        role: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a direct LLM answer when no worker agent produced one.

        This is the safety net that guarantees the user always receives a
        real, helpful response instead of an empty string.

        Args:
            query: User query
            role: User role
            context: Optional conversation context

        Returns:
            Response text (never empty unless generation itself fails)
        """
        context_str = ""
        if context:
            context_str = f"\n\nContext: {str(context)[:500]}"

        prompt = f"""
        You are an enterprise AI customer support assistant helping a
        {role.replace('_', ' ')}. Answer the customer's message clearly,
        accurately, and helpfully.

        Customer message: "{query}"{context_str}

        Provide a concise, friendly answer. If you cannot help, say so and
        suggest contacting support.
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.4,
            )
            answer = response["content"][0].text.strip()
            return answer or (
                "I'm sorry, I couldn't generate a response. Please try again."
            )
        except Exception as e:
            logger.error(f"Fallback response generation failed: {e}")
            return "I'm sorry, I'm having trouble responding right now. Please try again in a moment."


# Create LangGraph state graph for visualization
def create_workflow_graph():
    """
    Create the LangGraph state graph for visualization.

    Returns:
        StateGraph instance
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", "planner_node")
    graph.add_node("faq_worker", "faq_worker_node")
    graph.add_node("rag_worker", "rag_worker_node")
    graph.add_node("summarize_worker", "summarize_worker_node")
    graph.add_node("reason_worker", "reason_worker_node")
    graph.add_node("critic", "critic_node")
    graph.add_node("memory", "memory_node")
    graph.add_node("respond", "respond_node")

    # Add edges
    graph.add_edge("planner", "faq_worker", condition=lambda s: s["query_type"] == QueryType.FAQ)
    graph.add_edge("planner", "rag_worker", condition=lambda s: s["query_type"] == QueryType.RAG)
    graph.add_edge("planner", "summarize_worker", condition=lambda s: s["query_type"] == QueryType.SUMMARIZE)
    graph.add_edge("planner", "reason_worker", condition=lambda s: s["query_type"] == QueryType.REASON)

    # All workers go to critic
    graph.add_edge("faq_worker", "critic")
    graph.add_edge("rag_worker", "critic")
    graph.add_edge("summarize_worker", "critic")
    graph.add_edge("reason_worker", "critic")

    # Critic goes to memory then respond
    graph.add_edge("critic", "memory")
    graph.add_edge("memory", "respond")

    # End
    graph.add_edge("respond", END)

    return graph


# Global workflow instance
chat_workflow: Optional[ChatWorkflow] = None


def get_chat_workflow(db_session=None) -> ChatWorkflow:
    """Get or create the global chat workflow instance."""
    global chat_workflow
    if chat_workflow is None:
        chat_workflow = ChatWorkflow(db_session)
    return chat_workflow