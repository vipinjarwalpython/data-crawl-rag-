import os
from pathlib import Path
from typing import Optional, Tuple, Any
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from app.core.config import settings
from app.core.logging import logger


class LLMManager:
    """Manager for loading and running the local Qwen/Qwen2.5-0.5B-Instruct LLM

    with local caching in models/llm, query reframing, and temperature control.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.DEFAULT_LLM_MODEL
        self.cache_dir = settings.BASE_DIR / settings.LLM_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._tokenizer = None
        self._model = None

    def load_model(self) -> Tuple[Any, Any]:
        """Lazy load tokenizer and causal language model from local cache or Hugging Face."""
        if self._model is None or self._tokenizer is None:
            logger.info(f"Loading local LLM '{self.model_name}' (cache: {self.cache_dir})...")
            os.environ["HF_HOME"] = str(self.cache_dir)
            
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=str(self.cache_dir),
                trust_remote_code=True
            )
            
            # Use torch bfloat16 or float32 for CPU/GPU compatibility
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=str(self.cache_dir),
                torch_dtype=torch_dtype,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )
            logger.info(f"LLM '{self.model_name}' loaded successfully.")
        
        return self._tokenizer, self._model

    def is_cached_locally(self) -> bool:
        """Check if LLM files exist locally."""
        if not self.cache_dir.exists():
            return False
        files = list(self.cache_dir.glob("**/*"))
        return len(files) > 0

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.2
    ) -> str:
        """Generate response using the LLM with temperature control for accuracy vs randomness."""
        try:
            tokenizer, model = self.load_model()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            formatted_prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            inputs = tokenizer([formatted_prompt], return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

            # Configure generation parameters (temperature, top_p, max_tokens)
            do_sample = temperature > 0.0
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=max(temperature, 0.01) if do_sample else None,
                do_sample=do_sample,
                top_p=0.9 if do_sample else None,
                pad_token_id=tokenizer.eos_token_id
            )

            # Decode only newly generated tokens
            generated_ids = outputs[0][len(inputs["input_ids"][0]):]
            response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
            return response_text.strip()

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}", exc_info=True)
            return f"Error generating response: {str(e)}"

    def reframe_query(self, user_query: str) -> str:
        """Reframe user query using LLM for optimized retrieval and keyword matching."""
        try:
            system_prompt = (
                "You are an AI search query optimization expert. "
                "Reframe the user's question into precise keywords and semantic search terms "
                "optimized for retrieval from a company knowledge base. "
                "Return ONLY the reframed query string without quotes or extra explanation."
            )
            prompt = f"User Query: {user_query}\nOptimized Search Query:"
            reframed = self.generate_response(prompt, system_prompt=system_prompt, max_tokens=150, temperature=0.1)
            print(f"Reframed Query: {reframed}")
            cleaned = reframed.strip('\"\'\n ')
            if not cleaned or len(cleaned) < 2:
                return user_query
            logger.info(f"Query reframed: '{user_query}' -> '{cleaned}'")
            return cleaned
        except Exception as e:
            logger.warning(f"Query reframing failed, falling back to original: {e}")
            return user_query


llm_manager = LLMManager()
