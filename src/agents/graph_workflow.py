import sys
import os
from typing import Dict, Any

# Add parent directory to path to allow running directly from this file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.extractor_agent import EntityExtractorAgent, RelationExtractorAgent
from agents.rdf_builder_agent import RDFBuilderAgent, GraphToolbox
from agents.validator_agent import ValidatorAgent


class RootAgent:
    """Root Agent that orchestrates and routes tasks to specialized sub-agents."""
    
    def __init__(
        self,
        entity_extractor: EntityExtractorAgent,
        relation_extractor: RelationExtractorAgent,
        rdf_builder: RDFBuilderAgent,
        validator: ValidatorAgent
    ):
        self.entity_extractor = entity_extractor
        self.relation_extractor = relation_extractor
        self.rdf_builder = rdf_builder
        self.validator = validator

    def run_pipeline(self, text: str, graph_id: str = "generated") -> Dict[str, Any]:
        """Coordinate the orchestration of extracting, mapping, and validating the RDF graph."""
        # 1. Initialize local execution state (toolbox)
        toolbox = GraphToolbox()

        # 2. Call EntityExtractorAgent
        entity_result = self.entity_extractor.run(text)
        entities = entity_result.entities

        # 3. Call RelationExtractorAgent passing the recognized entities
        relation_result = self.relation_extractor.run(text, entities)
        relations = relation_result.relations

        # 4. Call RDFBuilderAgent to perform step-by-step graph construction via tools
        builder_summary = self.rdf_builder.run(entities, relations, toolbox, graph_id)

        # 5. Extract constructed graph from toolbox state
        graph = toolbox.graphs.get(graph_id)
        if graph is None:
            # Fallback if the agent somehow named the graph differently or failed to call create_graph
            if toolbox.graphs:
                graph = list(toolbox.graphs.values())[0]
            else:
                # Create empty graph so pipeline doesn't crash
                toolbox.create_graph(graph_id)
                graph = toolbox.graphs[graph_id]

        # 6. Call ValidatorAgent on the constructed graph
        validation = self.validator.run(graph)

        return {
            "entities": entities,
            "relations": relations,
            "execution_log": toolbox.execution_log,
            "builder_summary": builder_summary,
            "graph": graph,
            "validation": validation,
            "turtle": graph.serialize("turtle")
        }


class RDFGraphWorkflow:
    """Orchestrator class wrapping the RootAgent for backward compatibility and server route integration."""
    
    def __init__(
        self,
        entity_extractor: EntityExtractorAgent,
        relation_extractor: RelationExtractorAgent,
        builder_agent: RDFBuilderAgent,
        validator_agent: ValidatorAgent
    ):
        self.root_agent = RootAgent(
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
            rdf_builder=builder_agent,
            validator=validator_agent
        )

    def run(self, text: str) -> Dict[str, Any]:
        result = self.root_agent.run_pipeline(text)
        # Re-structure slightly for backward compatibility with UI expectation
        return {
            "extraction": {
                "entities": result["entities"],
                "relations": result["relations"]
            },
            "execution_log": result["execution_log"],
            "graph": result["graph"],
            "validation": result["validation"],
            "turtle": result["turtle"]
        }


if __name__ == "__main__":
    # Test workflow locally
    print("Initializing Root Agent and Sub-Agents...")
    entity_extractor = EntityExtractorAgent()
    relation_extractor = RelationExtractorAgent()
    builder = RDFBuilderAgent()
    validator = ValidatorAgent()

    workflow = RDFGraphWorkflow(
        entity_extractor=entity_extractor,
        relation_extractor=relation_extractor,
        builder_agent=builder,
        validator_agent=validator
    )

    input_text = "Albert Einstein was born in Ulm, Germany, in 1879, and died in Princeton in 1955."
    print(f"\nRunning Root Agent pipeline with text: '{input_text}'")
    
    result = workflow.run(input_text)
    
    print("\n--- Extracted Entities ---")
    for ent in result["extraction"]["entities"]:
        print(f"- {ent.label} ({ent.type})")
        
    print("\n--- Extracted Relations ---")
    for rel in result["extraction"]["relations"]:
        print(f"- {rel.subject} --[{rel.predicate}]--> {rel.object}")
        
    print("\n--- Toolbox Execution Log (Tools Called) ---")
    for log in result["execution_log"]:
        print(f"🛠️  {log}")
        
    print("\n--- Validation Result ---")
    print(result["validation"].model_dump_json(indent=2))
    
    print("\n--- Generated Turtle ---")
    print(result["turtle"])
