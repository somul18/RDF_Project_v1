import sys
import os
from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.apps import App
from google.genai import types

# Add src to path so relative imports inside agents / tools resolve properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


class RDFPipelineAgent(BaseAgent):
    """ADK Agent wrapper around the multi-agent RDF semantic graph pipeline."""
    
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # User input text is typically the content of the last user event
        if not ctx.session.events or not ctx.session.events[-1].content:
            err_content = types.Content(parts=[types.Part.from_text(text="Error: No user message found.")])
            yield Event(author=self.name, content=err_content)
            return

        user_message = ""
        # Get content text from parts
        for part in ctx.session.events[-1].content.parts:
            if part.text:
                user_message += part.text
        
        # Import and execute our workflow pipeline
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
        
        try:
            res = workflow.run(user_message)
            # Yield the final Turtle serialization as the agent response
            resp_content = types.Content(parts=[types.Part.from_text(text=res["turtle"])])
            yield Event(author=self.name, content=resp_content)
        except Exception as e:
            err_resp = types.Content(parts=[types.Part.from_text(text=f"Error executing RDF pipeline: {e}")])
            yield Event(author=self.name, content=err_resp)


# Instantiate the root agent
root_agent = RDFPipelineAgent(name="rdf_pipeline_agent")

# Wrap it in the official ADK App class
app = App(
    root_agent=root_agent,
    name="adk_app",
)
