from enum import Enum


class Model(str, Enum):
    # ===== OpenAI Models (GPT-5.4 series) =====
    gpt_5_4 = "gpt-5.4"
    gpt_5_4_mini = "gpt-5.4-mini"
    gpt_5_4_nano = "gpt-5.4-nano"

    # ===== Google Gemini Models (stable) =====
    gemini_2_5_pro = "gemini-2.5-pro"
    gemini_2_5_flash = "gemini-2.5-flash"
    gemini_2_5_flash_lite = "gemini-2.5-flash-lite"

    # ===== Google Gemini Models (preview) =====
    gemini_3_1_pro = "gemini-3.1-pro-preview"
    gemini_3_flash = "gemini-3-flash-preview"

    # ===== Anthropic Claude Models =====
    claude_opus_4_6 = "claude-opus-4-6"
    claude_sonnet_4_6 = "claude-sonnet-4-6"
    claude_haiku_4_5 = "claude-haiku-4-5-20251001"


class ModelProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


def get_provider(model: Model) -> ModelProvider:
    """Determine provider from model enum."""
    model_value = model.value
    if model_value.startswith("gpt-"):
        return ModelProvider.OPENAI
    elif model_value.startswith("gemini-"):
        return ModelProvider.GEMINI
    elif model_value.startswith("claude-"):
        return ModelProvider.ANTHROPIC
    raise ValueError(f"Unknown provider for: {model_value}")


__all__ = ["Model", "ModelProvider", "get_provider"]
