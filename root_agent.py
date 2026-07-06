# ADK Root Agent for Multi-Agent RDF Pipeline
import sys
import os
from google.adk.agents import Agent
from google.adk.apps import App

# Add src to python path so imports of agents, tools, app etc. resolve properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

def run_rdf_pipeline(text: str) -> dict:
    """Run the multi-agent RDF semantic graph pipeline on the input text.
    
    Args:
        text: The input source text to extract the RDF semantic graph from.
        
    Returns:
        dict: A dictionary containing the 'turtle' serialization key.
    """
    from agents.graph_workflow import RDFGraphWorkflow
    from agents.extractor_agent import EntityExtractorAgent, RelationExtractorAgent
    from agents.rdf_builder_agent import RDFBuilderAgent
    from agents.validator_agent import ValidatorAgent
    from agents.critic_agent import CriticAgent
    
    workflow = RDFGraphWorkflow(
        EntityExtractorAgent(),
        RelationExtractorAgent(),
        RDFBuilderAgent(),
        ValidatorAgent(),
        CriticAgent()
    )
    
    res = workflow.run(text)
    return {"turtle": res["turtle"]}

# Instantiate the root agent as a standard Agent (LlmAgent)
root_agent = Agent(
    name="rdf_pipeline_agent",
    model="gemini-2.5-flash",
    instruction="When the user provides a text, run the run_rdf_pipeline tool on it, and output the final Turtle serialization.",
    tools=[run_rdf_pipeline]
)

# Wrap it in the official ADK App class
app = App(
    root_agent=root_agent,
    name="adk_app",
)
