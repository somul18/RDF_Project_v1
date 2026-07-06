from typing import List, Union, Any, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

from app.models.rdf import RDFGraph
from agents.extractor_agent import ExtractedEntity, ExtractedRelation

load_dotenv('/Users/johnpunin/jpunin/Programming/RDF_Project_v1/.env')


class GraphToolbox:
    """Provides standard RDF construction backend functions exposed as tools for AI agents."""
    
    def __init__(self):
        self.graphs = {}
        self.execution_log = []

    def create_graph(self, graph_id: str) -> str:
        """Create a new RDF graph in the toolbox.

        Args:
            graph_id: The unique identifier for the new graph (e.g. 'generated' or 'people').
        """
        if graph_id in self.graphs:
            msg = f"Graph '{graph_id}' already exists."
            self.execution_log.append(msg)
            return msg
        
        g = RDFGraph(graph_id=graph_id)
        # Bind standard namespaces by default
        g.bind("ex", "http://example.org/")
        g.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        g.bind("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
        g.bind("foaf", "http://xmlns.com/foaf/0.1/")
        g.bind("schema", "http://schema.org/")
        g.bind("xsd", "http://www.w3.org/2001/XMLSchema#")
        
        self.graphs[graph_id] = g
        msg = f"Successfully created graph '{graph_id}' with standard prefixes bound."
        self.execution_log.append(msg)
        return msg

    def bind_namespace(self, graph_id: str, prefix: str, uri: str) -> str:
        """Bind a namespace prefix to a URI in the graph.

        Args:
            graph_id: The identifier of the graph.
            prefix: The prefix string (e.g. 'ex' or 'foaf').
            uri: The full namespace URI (e.g. 'http://example.org/').
        """
        if graph_id not in self.graphs:
            msg = f"Error: Graph '{graph_id}' does not exist. Call create_graph first."
            self.execution_log.append(msg)
            return msg
        try:
            self.graphs[graph_id].bind(prefix, uri)
            msg = f"Bound prefix '{prefix}' to URI '{uri}' in graph '{graph_id}'."
            self.execution_log.append(msg)
            return msg
        except Exception as e:
            msg = f"Error binding namespace: {e}"
            self.execution_log.append(msg)
            return msg

    def add_type(self, graph_id: str, subject: str, type_node: str) -> str:
        """Add an rdf:type relation between a subject resource and a type class.

        Args:
            graph_id: The identifier of the graph.
            subject: The subject resource URI or prefix-notation URI (e.g. 'ex:Marie_Curie').
            type_node: The type class URI or prefix-notation URI (e.g. 'foaf:Person').
        """
        if graph_id not in self.graphs:
            msg = f"Error: Graph '{graph_id}' does not exist. Call create_graph first."
            self.execution_log.append(msg)
            return msg
        try:
            self.graphs[graph_id].add_type(subject, type_node)
            msg = f"Added type '{type_node}' to subject '{subject}' in graph '{graph_id}'."
            self.execution_log.append(msg)
            return msg
        except Exception as e:
            msg = f"Error adding type: {e}"
            self.execution_log.append(msg)
            return msg

    def add_literal(
        self,
        graph_id: str,
        subject: str,
        predicate: str,
        value: str,
        datatype: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """Add a literal value relation (triple) to the graph.

        Args:
            graph_id: The identifier of the graph.
            subject: The subject resource URI (e.g. 'ex:Marie_Curie').
            predicate: The predicate property URI (e.g. 'ex:birthYear').
            value: The literal value as a string (e.g. '1867' or 'Warsaw'). If numeric or boolean, it will be coerced.
            datatype: Optional datatype URI or prefix (e.g. 'xsd:integer', 'xsd:double', 'xsd:boolean').
            language: Optional language tag (e.g. 'en').
        """
        if graph_id not in self.graphs:
            msg = f"Error: Graph '{graph_id}' does not exist. Call create_graph first."
            self.execution_log.append(msg)
            return msg
        try:
            # Type coerce numbers/booleans from string value if possible
            coerced_val = value
            if datatype in ("xsd:integer", "http://www.w3.org/2001/XMLSchema#integer"):
                try: coerced_val = int(value)
                except ValueError: pass
            elif datatype in ("xsd:double", "http://www.w3.org/2001/XMLSchema#double"):
                try: coerced_val = float(value)
                except ValueError: pass
            elif datatype in ("xsd:boolean", "http://www.w3.org/2001/XMLSchema#boolean"):
                coerced_val = value.lower() in ("true", "1", "yes")
            else:
                # auto-detect numbers if no datatype is specified
                if value.isdigit():
                    coerced_val = int(value)
                else:
                    try:
                        coerced_val = float(value)
                    except ValueError:
                        pass
            
            self.graphs[graph_id].add_literal(subject, predicate, coerced_val, datatype, language)
            msg = f"Added literal triple ({subject}, {predicate}, {coerced_val}) in graph '{graph_id}'."
            self.execution_log.append(msg)
            return msg
        except Exception as e:
            msg = f"Error adding literal: {e}"
            self.execution_log.append(msg)
            return msg

    def add_triple(self, graph_id: str, subject: str, predicate: str, object_val: str) -> str:
        """Add a relation between two resources (subjects/objects) in the graph.

        Args:
            graph_id: The identifier of the graph.
            subject: The subject resource URI (e.g. 'ex:Marie_Curie').
            predicate: The predicate property URI (e.g. 'ex:birthPlace').
            object_val: The object resource URI (e.g. 'ex:Warsaw').
        """
        if graph_id not in self.graphs:
            msg = f"Error: Graph '{graph_id}' does not exist. Call create_graph first."
            self.execution_log.append(msg)
            return msg
        try:
            self.graphs[graph_id].add(subject, predicate, object_val)
            msg = f"Added relation triple ({subject}, {predicate}, {object_val}) in graph '{graph_id}'."
            self.execution_log.append(msg)
            return msg
        except Exception as e:
            msg = f"Error adding relation: {e}"
            self.execution_log.append(msg)
            return msg


class RDFBuilderAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name

    def run(
        self,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
        toolbox: GraphToolbox,
        graph_id: str = "generated"
    ) -> str:
        """Construct the RDF graph by executing backend tool functions based on extracted data."""
        
        entities_data = "\n".join([f"- ID: {e.id}, Label: {e.label}, Type: {e.type}" for e in entities])
        relations_data = "\n".join([f"- Subject: {r.subject}, Predicate: {r.predicate}, Object: {r.object}" for r in relations])
        
        system_instruction = """
        You are an expert RDF Graph Builder Agent.
        Your goal is to build an RDF graph using the provided toolbox tools.
        
        Follow these steps:
        1. Initialize the graph using `create_graph`.
        2. Map the extracted entities to appropriate standard classes (using `add_type`):
           - Use standard prefixes where appropriate: foaf:Person, schema:Place, schema:Event, etc.
           - Prepend 'ex:' to local entity resource IDs (e.g., entity ID 'Marie_Curie' becomes 'ex:Marie_Curie').
        3. Map the extracted relations to triples:
           - If the object of the relation is another entity, call `add_triple` (e.g. subject: 'ex:Marie_Curie', predicate: 'schema:birthPlace', object: 'ex:Warsaw').
           - If the object is a literal (like a year or a string that is not an entity ID), call `add_literal` (e.g. subject: 'ex:Marie_Curie', predicate: 'schema:birthDate', value: '1867', datatype: 'xsd:integer').
        """
        
        prompt = f"""
        Here is the extracted entity and relation data.
        Please construct the graph '{graph_id}' using the tools.
        
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
