def estimate_cost(usage: dict) -> str:
    """
    Quick cost estimate using OpenRouter page prices for z-ai/glm-4.5 as of Jul 25, 2025.
    0.20 per million input, 0.80 per million output.
    Falls back across common usage keys reported by different providers.
    """
    in_t = (
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("total_prompt_tokens")
        or 0
    )
    out_t = (
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("total_completion_tokens")
        or 0
    )
    reasoning_t = usage.get("reasoning_tokens") or usage.get("total_reasoning_tokens") or 0

    cost = in_t * 0.20 / 1_000_000 + out_t * 0.80 / 1_000_000

    if reasoning_t:
        return f"tokens in {in_t}, out {out_t}, reasoning {reasoning_t}, est cost ${cost:.4f}"
    return f"tokens in {in_t}, out {out_t}, est cost ${cost:.4f}"