import os
from typing import List, Union
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))


class ExtractedEntity(BaseModel):
    id: str = Field(..., description="Unique alphanumeric ID, no spaces (e.g. Marie_Curie)")
    label: str = Field(..., description="Human-readable label (e.g. Marie Curie)")
    type: str = Field(..., description="Type/Category of the entity (e.g. Person, Place, Event)")


class EntityExtractionResult(BaseModel):
    entities: List[ExtractedEntity]


class ExtractedRelation(BaseModel):
    subject: str = Field(..., description="ID of the subject entity")
    predicate: str = Field(..., description="CamelCase predicate representing the relationship (e.g. birthPlace, birthYear)")
    object: Union[str, int, float, bool] = Field(..., description="ID of the object entity or a literal value like 1867")


class RelationExtractionResult(BaseModel):
    relations: List[ExtractedRelation]


class EntityExtractorAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(self, text: str) -> EntityExtractionResult:
        """Extract unique entities with identifiers, labels, and types from the text."""
        prompt = f"""
        Analyze the following text and extract all unique entities.
        For each entity, generate:
        1. A unique identifier (snake_case or camelCase, no spaces, e.g. Marie_Curie).
        2. A human-readable label (e.g. Marie Curie).
        3. A general type/category (e.g. Person, Place, Event, Organization).
        
        Text to analyze:
        "{text}"
        """
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EntityExtractionResult,
                temperature=0.1
            )
        )
        
        return EntityExtractionResult.model_validate_json(response.text)


class RelationExtractorAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(self, text: str, entities: List[ExtractedEntity]) -> RelationExtractionResult:
        """Extract relationships between the given entities, or between entities and literal values."""
        entities_str = "\n".join([f"- ID: {e.id}, Label: {e.label}, Type: {e.type}" for e in entities])
        
        prompt = f"""
        Analyze the text below to extract semantic relations.
        Use ONLY the following recognized entities as subjects:
        {entities_str}
        
        The object of the relation can be:
        - The ID of another entity from the recognized list.
        - A literal value (number, boolean, or string, e.g. 1867).
        
        For each relation, output:
        1. subject: The ID of the subject entity.
        2. predicate: A camelCase relation verb/property (e.g. birthPlace, birthYear, foundedBy).
        3. object: The ID of the target entity OR a literal value.
        
        Text to analyze:
        "{text}"
        """
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RelationExtractionResult,
                temperature=0.1
            )
        )
        
        return RelationExtractionResult.model_validate_json(response.text)
