from typing import List, Union, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

from app.models.rdf import RDFGraph
from agents.extractor_agent import ExtractionResult

load_dotenv()


class MappedEntity(BaseModel):
    id: str
    type_uri: str = Field(..., description="Mapped type class, prefer standard prefixes (e.g. foaf:Person, ex:Place, schema:Event)")


class MappedRelation(BaseModel):
    subject: str
    predicate_uri: str = Field(..., description="Mapped predicate property, prefer standard prefixes (e.g. ex:birthPlace, schema:birthDate)")
    object: Union[str, int, float, bool]


class MappingResult(BaseModel):
    entities: List[MappedEntity]
    relations: List[MappedRelation]


class RDFBuilderAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(self, extraction: ExtractionResult, graph_id: str = "generated") -> RDFGraph:
        """Map extracted JSON structures to standard RDF vocabularies and construct an RDFGraph."""
        prompt = f"""
        Map the following extracted entities and relations to RDF terms.
        Use standard prefixes where appropriate:
        - rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
        - rdfs: http://www.w3.org/2000/01/rdf-schema#
        - foaf: http://xmlns.com/foaf/0.1/
        - schema: http://schema.org/
        - xsd: http://www.w3.org/2001/XMLSchema#
        - ex: http://example.org/ (for custom/local resources and predicates)
        
        Extraction data:
        {extraction.model_dump_json(indent=2)}
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MappingResult,
                temperature=0.1
            )
        )

        mapping = MappingResult.model_validate_json(response.text)

        # Build the graph
        graph = RDFGraph(graph_id=graph_id)
        
        # Bind standard namespaces
        graph.bind("ex", "http://example.org/")
        graph.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        graph.bind("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
        graph.bind("foaf", "http://xmlns.com/foaf/0.1/")
        graph.bind("schema", "http://schema.org/")
        graph.bind("xsd", "http://www.w3.org/2001/XMLSchema#")

        # Get set of all extracted entity IDs for object resource resolution
        entity_ids = {ent.id for ent in extraction.entities}

        # Add types
        for ent in mapping.entities:
            subj_uri = f"ex:{ent.id}"
            graph.add_type(subj_uri, ent.type_uri)

        # Add relations
        for rel in mapping.relations:
            subj_uri = f"ex:{rel.subject}"
            
            # Check if object is an entity ID, meaning it's a resource (IRI)
            if isinstance(rel.object, str) and rel.object in entity_ids:
                obj_uri = f"ex:{rel.object}"
                graph.add(subj_uri, rel.predicate_uri, obj_uri)
            else:
                # Add as literal
                graph.add_literal(subj_uri, rel.predicate_uri, rel.object)

        return graph
