from typing import List, Union, Any, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

from agents.extractor_agent import ExtractedEntity, ExtractedRelation
from tools.graph_tools import GraphToolbox


class RDFBuilderAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(
        self,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
        toolbox: GraphToolbox,
        graph_id: str = "generated",
        critic_feedback: Optional[List[str]] = None
    ) -> str:
        """Construct the RDF graph by executing backend tool functions based on extracted data and critic feedback."""
        
        entities_data = "\n".join([f"- ID: {e.id}, Label: {e.label}, Type: {e.type}" for e in entities])
        relations_data = "\n".join([f"- Subject: {r.subject}, Predicate: {r.predicate}, Object: {r.object}" for r in relations])
        
        feedback_prompt = ""
        if critic_feedback:
            feedback_str = "\n".join([f"- {fb}" for fb in critic_feedback])
            feedback_prompt = f"""
            CRITICAL FEEDBACK FOR CORRECTION:
            A Critic Agent reviewed your previous graph and identified these issues.
            You MUST fix these by calling the appropriate tools (e.g. `add_literal` with explicit datatypes, `add_triple`, etc.):
            {feedback_str}
            """

        system_instruction = """
        You are an expert RDF Graph Builder Agent.
        Your goal is to build or correct an RDF graph using the provided toolbox tools.
        
        Follow these steps:
        1. Initialize the graph using `create_graph` (if it does not exist yet. If it already exists, do NOT call create_graph).
        2. Map the extracted entities to appropriate standard classes (using `add_type`):
           - Use standard prefixes where appropriate: foaf:Person, schema:Place, schema:Event, etc.
           - Prepend 'ex:' to local entity resource IDs (e.g., entity ID 'Marie_Curie' becomes 'ex:Marie_Curie').
        3. Map the extracted relations to triples:
           - If the object of the relation is another entity, call `add_triple` (e.g. subject: 'ex:Marie_Curie', predicate: 'schema:birthPlace', object: 'ex:Warsaw').
           - If the object is a literal (like a year or a string that is not an entity ID), call `add_literal` (e.g. subject: 'ex:Marie_Curie', predicate: 'schema:birthDate', value: '1867', datatype: 'xsd:integer').
        """
        
        prompt = f"""
        Here is the extracted entity and relation data.
        Please construct or modify the graph '{graph_id}' using the tools.
        
        {feedback_prompt}
        
        Entities:
        {entities_data}
        
        Relations:
        {relations_data}
        """

        # Bind tools to the generation config.
        # The GenAI SDK will automatically declare and handle calling execution for these.
        config = types.GenerateContentConfig(
            tools=[
                toolbox.create_graph,
                toolbox.bind_namespace,
                toolbox.add_type,
                toolbox.add_literal,
                toolbox.add_triple
            ],
            system_instruction=system_instruction,
            temperature=0.1
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        
        return response.text
