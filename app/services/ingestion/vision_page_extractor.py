"""Optional multimodal page extraction for charts, formulas, and image-heavy PDF pages."""
import base64
import io

import litellm

from app.config import settings


VISION_PROMPT = """You are extracting knowledge from a PDF page image for retrieval.

Return a concise but information-dense plain text description of the page.
Prioritize:
- chart titles, axes, legends, and the main takeaway
- formulas, variables, and equation relationships
- table headers and key values
- diagram labels and any explicit quantitative facts

Do not invent unreadable details. If something is unclear, say it is unclear.
Output plain text only."""


def extract_page_with_vision(page) -> str:
    """Extract structured text from an image-heavy PDF page via a vision model."""
    if not settings.PDF_VISION_ENABLED:
        return ""

    page_image = page.to_image(resolution=settings.PDF_VISION_RENDER_DPI)
    image = page_image.original
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    response = litellm.completion(
        model=f"openai/{settings.PDF_VISION_MODEL}",
        api_base=settings.LITELLM_PROXY_URL,
        api_key="sk-fake-key",
        timeout=settings.PDF_VISION_TIMEOUT_SEC,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                ],
            }
        ],
        max_tokens=500,
        temperature=0.0,
    )
    return (response.choices[0].message.content or "").strip()
