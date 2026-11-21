import os
from dotenv import load_dotenv
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from utils.config_loader import load_config
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from logger.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    def __init__(self):
        self.config = load_config()
        logger.debug("Config loaded")
    
    def __getitem__(self, key):
        return self.config[key]

class ModelLoader(BaseModel):
    model_provider: Literal["groq", "gemini"] = "groq"
    config: Optional[ConfigLoader] = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        self.config = ConfigLoader()
    
    class Config:
        arbitrary_types_allowed = True
    
    def load_llm(self):
        """
        Load and return the LLM model.
        """
        if self.model_provider == "groq":
            groq_api_key = os.getenv("GROQ_API_KEY")
            model_name = self.config["llm"]["groq"]["model_name"]
            if not groq_api_key:
                logger.error("GROQ_API_KEY is not set")
            llm=ChatGroq(model=model_name, api_key=groq_api_key, timeout=60, max_retries=2)
            logger.info("Loaded Groq model %s (timeout=60s, max_retries=2)", model_name)
        elif self.model_provider == "gemini":
            gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not gemini_api_key:
                logger.error("Neither GEMINI_API_KEY nor GOOGLE_API_KEY is set")
            gemini_cfg = self.config["llm"]["gemini"]
            llm = ChatGoogleGenerativeAI(
                model=gemini_cfg["model_name"],
                google_api_key=gemini_api_key,
                timeout=gemini_cfg.get("timeout", 60),
                max_retries=gemini_cfg.get("max_retries", 2),
                thinking_budget=gemini_cfg.get("thinking_budget"),
            )
            logger.info(
                "Loaded Gemini model %s (timeout=%ss, max_retries=%s, thinking_budget=%s)",
                gemini_cfg["model_name"], gemini_cfg.get("timeout", 60),
                gemini_cfg.get("max_retries", 2), gemini_cfg.get("thinking_budget"),
            )
        else:
            logger.error("Unsupported model provider: %s", self.model_provider)
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
        
        return llm
    