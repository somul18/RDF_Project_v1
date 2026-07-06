from typing import List, Union
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


class ExtractedEntity(BaseModel):
    id: str = Field(..., description="Unique alphanumeric ID, no spaces (e.g. Marie_Curie)")
    label: str = Field(..., description="Human-readable label (e.g. Marie Curie)")
    type: str = Field(..., description="Type/Category of the entity (e.g. Person, Place, Event)")


class ExtractedRelation(BaseModel):
    subject: str = Field(..., description="ID of the subject entity")
    predicate: str = Field(..., description="CamelCase predicate representing the relationship (e.g. birthPlace, birthYear)")
    object: Union[str, int, float, bool] = Field(..., description="ID of the object entity or a literal value like 1867")


class ExtractionResult(BaseModel):
    entities: List[ExtractedEntity]
    relations: List[ExtractedRelation]


class ExtractorAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(self, text: str) -> ExtractionResult:
        """Analyze text to extract entities and their relations in a structured JSON format."""
        prompt = f"""
        Analyze the following text and extract:
        1. Entities with a unique identifier (snake_case/camelCase, no spaces), label, and type.
        2. Relations between these entities or between entities and literal values.
        
        Text to analyze:
        "{text}"
        """
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractionResult,
                temperature=0.1
            )
        )
        
        # Pydantic validates the JSON response automatically
        return ExtractionResult.model_validate_json(response.text)
