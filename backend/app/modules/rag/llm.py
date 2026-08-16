"""
Local LLM manager for CrawlRAG.

Handles lazy loading of the Qwen2.5-0.5B-Instruct model with:
- Atomic load (both tokenizer AND model succeed or both are reset)
- Token-count logging per generation call
- Separate LLMOutputCleaner utility class for output post-processing
- Query reframing for improved retrieval recall
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.core.config import settings
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# LLM Output Cleaner  (standalone utility — not coupled to LLMManager)
# ---------------------------------------------------------------------------

class LLMOutputCleaner:
    """Post-processes raw LLM output into clean, natural, human-readable text.

    Removes robotic meta-commentary, code artifacts, escaped characters,
    and trailing disclaimers that small language models tend to produce.
    """

    # Regex patterns for leading robotic clauses to strip.
    _LEADING_ROBOTIC_PATTERNS = [
        r"(?i)^i'm\s+sorry,?\s*(?:but\s*)?(?:i\s+cannot|i\s+can't|i\s+am\s+unable)[^.\n]*?(?:,\s*|\.\s*|:\s*|\n+)",
        r"(?i)^as\s+there\s+(?:isn't|is\s+no|are\s+no)[^.\n]*?(?:,\s*|\.\s*|:\s*|\n+)",
        r"(?i)^(?:based\s+on|according\s+to|in|from)\s+(?:the\s+)?(?:provided|given|above|these)?\s*"
        r"(?:context|information|snippets?|text|data|documents?)[^.\n]*?(?:,\s*|\.\s*|:\s*|\n+)",
        r"(?i)^as\s+(?:mentioned|stated|seen|noted|indicated)\s+in\s+(?:the\s+)?"
        r"(?:provided|given|above)?\s*(?:context|snippets?|text)[^.\n]*?(?:,\s*|\.\s*|:\s*|\n+)",
        r"(?i)^(?:here\s+is|here\s+are|sure,?\s*(?:here\s+is|here\s+are|i\s+can\s+provide)?)[^.\n]*?(?::\s*|\n+)",
        r"(?i)^(?:answer|direct\s+answer|accurate\s+answer)\s*:\s*",
    ]

    # Regex patterns for trailing disclaimer sentences to strip.
    _TRAILING_DISCLAIMER_PATTERNS = [
        r"(?i)(?:please\s+)?clarify\s+which.*$",
        r"(?i)(?:please\s+)?feel\s+free\s+to\s+ask.*$",
        r"(?i)(?:please\s+)?let\s+me\s+know\s+if\s+you\s+need.*$",
        r"(?i)(?:if\s+you\s+need\s+anything\s+else|if\s+you\s+have\s+further\s+questions).*$",
    ]

    @classmethod
    def clean(cls, raw_text: str) -> str:
        """Return a cleaned version of *raw_text* free of LLM artifacts.

        Processing steps:
        1. Strip code comments (``//``, ``/* */``, ``<!-- -->``)
        2. Remove stray backslashes and escaped quote sequences
        3. Collapse duplicate quote characters
        4. Remove leading robotic meta-commentary clauses
        5. Remove trailing disclaimer sentences
        6. Strip wrapping outer quotes from the whole answer
        7. Normalise lines and whitespace
        """
        if not raw_text:
            return ""

        cleaned = raw_text.strip()

        # Step 1: remove code comment artifacts.
        cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)

        # Step 2: remove escaped characters and stray backslashes.
        cleaned = cleaned.replace(r'\"', '"').replace(r"\'", "'")
        cleaned = re.sub(r"\\+", "", cleaned)

        # Step 3: collapse duplicate quote characters.
        cleaned = re.sub(r'"+', '"', cleaned)

        # Step 4: strip leading robotic clauses.
        for pattern in cls._LEADING_ROBOTIC_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned).strip()

        # Step 5: strip trailing disclaimers.
        for pattern in cls._TRAILING_DISCLAIMER_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE).strip()

        # Step 6: strip wrapping quotes around the entire answer.
        if len(cleaned) > 2 and (
            (cleaned.startswith('"') and cleaned.endswith('"'))
            or (cleaned.startswith("'") and cleaned.endswith("'"))
        ):
            cleaned = cleaned[1:-1].strip()

        # Step 7: normalise lines — strip per-line edge quotes and noise.
        cleaned_lines = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            # Remove edge quote characters from individual lines.
            line = re.sub(r'^[\"\']+|[\"\']+$', "", line).strip()
            # Remove double-slash noise inside a line.
            line = re.sub(r"//+", "", line).strip()
            if line:
                cleaned_lines.append(line)

        return "\n\n".join(cleaned_lines)


# ---------------------------------------------------------------------------
# LLM Manager
# ---------------------------------------------------------------------------

class LLMManager:
    """Lazy-loading manager for the local Qwen2.5-0.5B-Instruct causal LLM.

    Model and tokenizer are loaded atomically — if either fails, both are
    reset to None so that the next call retries the full load instead of
    operating in a partially-initialised state.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name: str = model_name or settings.DEFAULT_LLM_MODEL
        self.cache_dir: Path = settings.resolve_path(settings.LLM_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._tokenizer: Optional[Any] = None
        self._model: Optional[Any] = None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> Tuple[Any, Any]:
        """Lazily load the tokenizer and causal language model.

        The load is **atomic**: if the model load fails after the tokenizer
        has already succeeded, the tokenizer is also reset to None.
        This prevents the ``_tokenizer is not None but _model is None`` bug.
        """
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model

        logger.info(
            "Loading LLM '%s' from cache '%s' …",
            self.model_name,
            self.cache_dir,
        )
        os.environ["HF_HOME"] = str(self.cache_dir)

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=str(self.cache_dir),
                trust_remote_code=True,
            )

            # Use float16 on CUDA for speed; float32 on CPU for stability.
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            device_map = "auto" if torch.cuda.is_available() else None

            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=str(self.cache_dir),
                torch_dtype=torch_dtype,
                device_map=device_map,
                trust_remote_code=True,
            )

            # Commit only after both succeed.
            self._tokenizer = tokenizer
            self._model = model

            logger.info(
                "LLM '%s' loaded successfully (device=%s, dtype=%s).",
                self.model_name,
                next(model.parameters()).device,
                torch_dtype,
            )

        except Exception as exc:
            # Atomic reset — no partial state.
            self._tokenizer = None
            self._model = None
            logger.error(
                "Failed to load LLM '%s': %s",
                self.model_name,
                exc,
                exc_info=True,
            )
            raise

        return self._tokenizer, self._model

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 0,
        temperature: float = 0.0,
    ) -> str:
        """Generate a text response for *prompt* using the local LLM.

        Parameters
        ----------
        prompt:
            The user-facing question or instruction.
        system_prompt:
            Optional system-role instruction prepended to the conversation.
        max_new_tokens:
            Maximum tokens to generate.  Defaults to ``settings.LLM_MAX_NEW_TOKENS``.
        temperature:
            Sampling temperature.  ``0.0`` → greedy / deterministic.
            Defaults to ``settings.LLM_TEMPERATURE``.
        """
        resolved_max_tokens = max_new_tokens or settings.LLM_MAX_NEW_TOKENS
        resolved_temperature = temperature if temperature > 0.0 else settings.LLM_TEMPERATURE

        try:
            tokenizer, model = self.load_model()

            conversation_messages = []
            if system_prompt:
                conversation_messages.append({"role": "system", "content": system_prompt})
            conversation_messages.append({"role": "user", "content": prompt})

            formatted_prompt: str = tokenizer.apply_chat_template(
                conversation_messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            model_inputs = tokenizer([formatted_prompt], return_tensors="pt")
            input_token_count = model_inputs["input_ids"].shape[1]

            if torch.cuda.is_available():
                model_inputs = {key: tensor.to(model.device) for key, tensor in model_inputs.items()}

            # Use greedy decoding when temperature ≤ 0, sampling otherwise.
            use_sampling = resolved_temperature > 0.0
            generation_output = model.generate(
                **model_inputs,
                max_new_tokens=resolved_max_tokens,
                temperature=resolved_temperature if use_sampling else None,
                do_sample=use_sampling,
                top_p=0.9 if use_sampling else None,
                pad_token_id=tokenizer.eos_token_id,
            )

            # Decode only the newly generated tokens (exclude the prompt).
            generated_token_ids = generation_output[0][model_inputs["input_ids"].shape[1]:]
            response_text = tokenizer.decode(generated_token_ids, skip_special_tokens=True)

            output_token_count = len(generated_token_ids)
            logger.debug(
                "LLM generation: input_tokens=%d, output_tokens=%d, temperature=%.2f.",
                input_token_count,
                output_token_count,
                resolved_temperature,
            )

            return response_text.strip()

        except Exception as exc:
            logger.error("LLM response generation failed: %s", exc, exc_info=True)
            return f"Error generating response: {exc}"

    # ------------------------------------------------------------------
    # Query optimisation
    # ------------------------------------------------------------------

    def reframe_query_for_retrieval(self, user_query: str) -> str:
        """Reframe *user_query* into optimised retrieval keywords using the LLM.

        Returns the original query unchanged if reframing fails or produces
        an empty / identical result.
        """
        try:
            system_prompt = (
                "You are a search query optimisation expert. "
                "Reframe the user's question into precise keywords and semantic "
                "search terms optimised for retrieval from a company knowledge base. "
                "Return ONLY the reframed query string — no quotes, no explanation."
            )
            prompt = f"User Query: {user_query}\nOptimized Search Query:"

            raw_reframed = self.generate_response(
                prompt=prompt,
                system_prompt=system_prompt,
                max_new_tokens=100,
                temperature=0.05,
            )
            reframed_query = raw_reframed.strip("\"'\n ")

            if not reframed_query or len(reframed_query) < 2:
                return user_query

            if reframed_query.lower().strip() == user_query.lower().strip():
                return user_query

            logger.info(
                "Query reframed: '%s' -> '%s'.",
                user_query,
                reframed_query,
            )
            return reframed_query

        except Exception as exc:
            logger.warning(
                "Query reframing failed — falling back to original query. Error: %s",
                exc,
            )
            return user_query

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def is_model_loaded(self) -> bool:
        """Return True if both tokenizer and model are fully loaded."""
        return self._tokenizer is not None and self._model is not None

    def is_cached_locally(self) -> bool:
        """Return True if LLM files exist in the local cache directory."""
        return self.cache_dir.exists() and any(self.cache_dir.iterdir())

    def get_model_info(self) -> Dict[str, Any]:
        """Return a diagnostic summary of the current LLM state."""
        return {
            "model_name": self.model_name,
            "is_loaded": self.is_model_loaded(),
            "is_cached_locally": self.is_cached_locally(),
            "cache_dir": str(self.cache_dir),
        }


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
llm_manager = LLMManager()
llm_output_cleaner = LLMOutputCleaner()
