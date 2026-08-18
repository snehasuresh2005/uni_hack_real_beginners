import os


def query_gemini(prompt):
    """Run a capped Gemini request; credentials stay in the environment/settings."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "256")), "temperature": 0},
        )
        return response.text.strip() if response and response.text else None
    except Exception as exc:
        print(f"Gemini query failed: {exc}")
        return None
