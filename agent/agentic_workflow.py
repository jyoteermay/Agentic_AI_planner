import time
from utils.model_loader import ModelLoader
from prompt_library.prompt import SYSTEM_PROMPT
from langgraph.graph import StateGraph, MessagesState, END, START
from langgraph.prebuilt import ToolNode, tools_condition
from tools.weather_info_tool import WeatherInfoTool
from tools.place_search_tool import PlaceSearchTool
from tools.expense_calculator_tool import CalculatorTool
from tools.currency_conversion_tool import CurrencyConverterTool
from logger.logging import get_logger

logger = get_logger(__name__)

class GraphBuilder():
    def __init__(self,model_provider: str = "groq"):
        self.model_loader = ModelLoader(model_provider=model_provider)
        self.llm = self.model_loader.load_llm()
        
        self.tools = []
        
        self.weather_tools = WeatherInfoTool()
        self.place_search_tools = PlaceSearchTool()
        self.calculator_tools = CalculatorTool()
        self.currency_converter_tools = CurrencyConverterTool()
        
        self.tools.extend([* self.weather_tools.weather_tool_list, 
                           * self.place_search_tools.place_search_tool_list,
                           * self.calculator_tools.calculator_tool_list,
                           * self.currency_converter_tools.currency_converter_tool_list])
        
        self.llm_with_tools = self.llm.bind_tools(tools=self.tools)
        
        self.graph = None
        
        self.system_prompt = SYSTEM_PROMPT
        logger.info(
            "GraphBuilder ready: provider=%s, %d tools: %s",
            model_provider, len(self.tools), ", ".join(t.name for t in self.tools),
        )
    
    
    def agent_function(self,state: MessagesState):
        """Main agent function"""
        user_question = state["messages"]
        input_question = [self.system_prompt] + user_question
        logger.debug("Calling LLM with %d messages", len(input_question))
        start = time.perf_counter()
        try:
            response = self.llm_with_tools.invoke(input_question)
        except Exception:
            logger.exception("LLM call failed after %.2fs", time.perf_counter() - start)
            raise
        elapsed = time.perf_counter() - start

        usage = getattr(response, "usage_metadata", None) or {}
        tokens = (
            f" (tokens in={usage.get('input_tokens')}, out={usage.get('output_tokens')})" if usage else ""
        )
        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            names = ", ".join(f"{c['name']}({c.get('args')})" for c in tool_calls)
            logger.info("LLM took %.2fs%s -> calling %d tool(s): %s", elapsed, tokens, len(tool_calls), names)
        else:
            logger.info("LLM took %.2fs%s -> final answer", elapsed, tokens)
        return {"messages": [response]}
    def build_graph(self):
        graph_builder=StateGraph(MessagesState)
        graph_builder.add_node("agent", self.agent_function)
        tool_node = ToolNode(tools=self.tools)

        def timed_tools(state: MessagesState):
            start = time.perf_counter()
            try:
                result = tool_node.invoke(state)
            except Exception:
                logger.exception("Tool execution failed after %.2fs", time.perf_counter() - start)
                raise
            for msg in result.get("messages", []):
                content = str(msg.content)
                status = getattr(msg, "status", "success")
                log = logger.warning if status == "error" else logger.info
                log("Tool %s -> %s, %d chars", getattr(msg, "name", "?"), status, len(content))
                logger.debug("Tool %s output: %.500s", getattr(msg, "name", "?"), content)
            logger.info("Tools finished in %.2fs", time.perf_counter() - start)
            return result

        graph_builder.add_node("tools", timed_tools)
        graph_builder.add_edge(START,"agent")
        graph_builder.add_conditional_edges("agent",tools_condition)
        graph_builder.add_edge("tools","agent")
        graph_builder.add_edge("agent",END)
        self.graph = graph_builder.compile()
        return self.graph
        
    def __call__(self):
        return self.build_graph()