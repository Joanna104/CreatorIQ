
import json
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ideas", tags=["Idea Generation"])

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"


class IdeaRequest(BaseModel):
    topic: str = "skincare"
    platform: str = "Instagram"
    audience: str = "skincare beginners"
    content_format: str = "Short video"
    goal: str = "Increase engagement"


class Idea(BaseModel):
    title: str
    concept: str
    hook: str
    structure: list[str]


class IdeaResponse(BaseModel):
    ideas: list[Idea]


@router.post("/generate", response_model=IdeaResponse)
def generate_ideas(payload: IdeaRequest):
    prompt = f"""
You are CreatorIQ, an AI coach for beginner content creators.

Generate exactly 3 DISTINCT content ideas.

Creator preferences:
Topic: {payload.topic}
Platform: {payload.platform}
Audience: {payload.audience}
Format: {payload.content_format}
Goal: {payload.goal}

Make each idea different in its approach.
Keep the ideas practical for a beginner.

Return valid JSON only, in this exact structure:
{{
  "ideas": [
    {{
      "title": "Short title",
      "concept": "Explain the idea",
      "hook": "Opening line to attract attention",
      "structure": [
        "Opening",
        "Main content",
        "Ending"
      ]
    }}
  ]
}}

Return exactly 3 ideas.
Do not include predicted views or engagement numbers.
"""

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "format": "json",
                "stream": False
            },
            timeout=120.0
        )
        response.raise_for_status()

        result = response.json()
        content = result["message"]["content"]
        data = json.loads(content)

        parsed = IdeaResponse(**data)

        if len(parsed.ideas) != 3:
            raise ValueError("AI did not return exactly 3 ideas.")

        return parsed

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cannot connect to Ollama. "
                "Check that Ollama is running."
            )
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="Ollama returned an error."
        ) from exc

    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI response was not in the expected format."
        ) from exc
