from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import asdict
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from .config import Settings

logger = logging.getLogger(__name__)


class InferenceService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._tokenizer = None
        self._model = None
        self._load_lock = threading.Lock()

    @property
    def model_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def model_info(self) -> dict[str, Any]:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return {
            "status": "ok",
            "model_name": self.settings.model_name,
            "model_loaded": self.model_loaded,
            "use_4bit": self.settings.use_4bit,
            "response_language": self.settings.response_language,
            "device": device,
        }

    async def generate(self, message: str, context: str = "", language: str | None = None) -> str:
        return await asyncio.to_thread(self._generate_sync, message, context, language)

    def _generate_sync(self, message: str, context: str, language: str | None) -> str:
        start_time = time.time()
        message = (message or "").strip()
        if not message:
            raise ValueError("message must not be empty")

        prompt_context = (context or "")[: self.settings.context_max_chars]
        resolved_language = self._resolve_response_language(message=message, requested_language=language)
        
        load_start = time.time()
        tokenizer, model = self._get_or_load_model()
        load_time = time.time() - load_start
        logger.info(f"Model load/retrieve: {load_time:.2f}s")

        chat_messages = [
            {
                "role": "system",
                "content": self._build_system_instruction(resolved_language),
            }
        ]
        if prompt_context:
            chat_messages.append({"role": "system", "content": prompt_context})
        chat_messages.append({"role": "user", "content": message})

        if hasattr(tokenizer, "apply_chat_template"):
            prompt_text = tokenizer.apply_chat_template(
                chat_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt_text = self._fallback_prompt(message=message, context=prompt_context)

        tokenize_start = time.time()
        inputs = tokenizer(prompt_text, return_tensors="pt")
        model_device = self._resolve_model_device(model)
        inputs = {key: value.to(model_device) for key, value in inputs.items()}
        tokenize_time = time.time() - tokenize_start
        logger.info(f"Tokenization: {tokenize_time:.2f}s")

        gen_start = time.time()
        with torch.no_grad():
            output = model.generate(
                **inputs,
                min_new_tokens=self.settings.min_new_tokens,
                max_new_tokens=self.settings.max_new_tokens,
                temperature=self.settings.temperature,
                top_p=self.settings.top_p,
                repetition_penalty=self.settings.repetition_penalty,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_time = time.time() - gen_start
        logger.info(f"Generation: {gen_time:.2f}s")

        generated_tokens = output[0][inputs["input_ids"].shape[-1] :]
        response = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        total_time = time.time() - start_time
        logger.info(f"Total inference time: {total_time:.2f}s")
        
        return response

    def _get_or_load_model(self):
        if self.model_loaded:
            return self._tokenizer, self._model

        with self._load_lock:
            if self.model_loaded:
                return self._tokenizer, self._model

            logger.info("Loading model", extra={"settings": asdict(self.settings)})

            tokenizer = AutoTokenizer.from_pretrained(self.settings.model_name, use_fast=True)
            model_kwargs: dict[str, Any] = {"device_map": "auto"}

            if torch.cuda.is_available():
                model_kwargs["torch_dtype"] = torch.float16
            else:
                model_kwargs["torch_dtype"] = torch.float32

            if self.settings.use_4bit and torch.cuda.is_available():
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
            elif self.settings.use_4bit and not torch.cuda.is_available():
                logger.warning("USE_4BIT is enabled but CUDA is unavailable; loading model without 4-bit quantization")

            model = AutoModelForCausalLM.from_pretrained(self.settings.model_name, **model_kwargs)
            model.eval()

            self._tokenizer = tokenizer
            self._model = model
            logger.info("Model loaded successfully", extra={"model_name": self.settings.model_name})

            return self._tokenizer, self._model

    @staticmethod
    def _fallback_prompt(message: str, context: str) -> str:
        base_instruction = (
            "You are a helpful technical assistant. "
            "Always respond in the target language requested by the user or system instruction."
        )
        if context:
            return (
                f"System:\n{base_instruction}\n\n"
                f"Context:\n{context}\n\n"
                f"User:\n{message}\n\nAssistant:\n"
            )
        return f"System:\n{base_instruction}\n\nUser:\n{message}\n\nAssistant:\n"

    def _build_system_instruction(self, language: str) -> str:
        base = (self.settings.system_prompt or "").strip()
        if not base:
            base = "You are a helpful technical assistant."
        language_hint = f"Response language: {language}."
        return f"{base} {language_hint}".strip()

    def _resolve_response_language(self, message: str, requested_language: str | None) -> str:
        if requested_language and requested_language.strip() and requested_language.strip().lower() != "auto":
            return requested_language.strip().lower()

        configured = (self.settings.response_language or "").strip().lower()
        if configured and configured != "auto":
            return configured

        return self._detect_message_language(message)

    @staticmethod
    def _detect_message_language(message: str) -> str:
        cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", message))
        latin_count = len(re.findall(r"[A-Za-z]", message))

        if cyrillic_count == 0 and latin_count == 0:
            return "ru"
        if cyrillic_count >= latin_count:
            return "ru"
        return "en"

    @staticmethod
    def _resolve_model_device(model) -> torch.device:
        if hasattr(model, "device"):
            return model.device
        if hasattr(model, "hf_device_map") and model.hf_device_map:
            first_device = next(iter(model.hf_device_map.values()))
            return torch.device(first_device)
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
