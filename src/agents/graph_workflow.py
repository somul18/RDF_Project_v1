import sys
import os

# Add parent directory to path to allow running directly from this file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.extractor_agent import ExtractorAgent
from agents.rdf_builder_agent import RDFBuilderAgent
from agents.validator_agent import ValidatorAgent


class RDFGraphWorkflow:
    def __init__(
        self,
        extractor_agent: ExtractorAgent,
        builder_agent: RDFBuilderAgent,
        validator_agent: ValidatorAgent,
    ):
        self.extractor_agent = extractor_agent
        self.builder_agent = builder_agent
        self.validator_agent = validator_agent

    def run(self, text: str):
        """Orchestrate the multi-agent extraction, mapping, and validation pipeline."""
        extraction = self.extractor_agent.run(text)
        graph = self.builder_agent.run(extraction)
        validation = self.validator_agent.run(graph)

        return {
            "extraction": extraction,
            "graph": graph,
            "validation": validation,
            "turtle": graph.serialize("turtle"),
        }


if __name__ == "__main__":
    # Test workflow
    print("Initializing Agents...")
    extractor = ExtractorAgent()
    builder = RDFBuilderAgent()
    validator = ValidatorAgent()

    workflow = RDFGraphWorkflow(extractor, builder, validator)

    input_text = "Marie Curie was born in Warsaw in 1867."
    print(f"\nRunning workflow with input text: '{input_text}'")
    
    result = workflow.run(input_text)
    
    print("\n--- Extraction Result ---")
    print(result["extraction"].model_dump_json(indent=2))
    
    print("\n--- Validation Result ---")
    print(result["validation"].model_dump_json(indent=2))
    
    print("\n--- Turtle Output ---")
    print(result["turtle"])
