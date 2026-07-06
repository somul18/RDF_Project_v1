from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv('/Users/johnpunin/jpunin/Programming/RDF_Project_v1/.env')


class CriticItem(BaseModel):
    aspect: str = Field(..., description="The aspect evaluated (e.g., 'Missing Entity', 'Literal Datatypes', 'Unsupported Relation', 'Prefix Consistency')")
    passed: bool = Field(..., description="True if the aspect passed, False otherwise")
    details: str = Field(..., description="Detailed explanation of the findings")


class CriticRecommendation(BaseModel):
    issue: str = Field(..., description="The problem identified")
    action: str = Field(..., description="The exact corrective action to take (e.g. 'Add literal birthDate with value 1867 for ex:Marie_Curie')")


class CriticReport(BaseModel):
    is_approved: bool = Field(..., description="True if the graph is highly accurate and does not require immediate corrections, False otherwise")
    overall_confidence: float = Field(..., description="Overall confidence score in the RDF graph from 0.0 (low) to 1.0 (high)")
    evaluations: List[CriticItem]
    recommendations: List[CriticRecommendation] = Field(default_factory=list)


class CriticAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(self, source_text: str, turtle_graph: str, validation_errors: str) -> CriticReport:
        """Critique the generated RDF graph against the original source text and syntactic validation."""
        
        prompt = f"""
        You are an expert RDF Critic Agent.
        Your job is to audit the generated RDF graph (represented in Turtle) against the original source text.
        
        Analyze:
        1. Are any entities from the source text missing in the graph?
        2. Are there any relationships in the graph that are NOT supported by the source text?
        3. Are namespace prefixes consistent and properly bound?
        4. Should any literal values have explicit datatypes (e.g., years/numbers as xsd:integer)?
        5. Does the graph contain any syntactic validation issues?
        
        Input Source Text:
        "{source_text}"
        
        Generated Turtle Graph:
        ```turtle
        {turtle_graph}
        ```
        
        Syntactic Validation Errors (if any):
        {validation_errors}
        
        Provide a structured critique report. If there are semantic inconsistencies, missing elements, or missing datatypes, set is_approved = False and provide specific, actionable recommendations.
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticReport,
                temperature=0.1
            )
        )
        
        return CriticReport.model_validate_json(response.text)
