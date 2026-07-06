import sys
import os
from typing import Dict, Any, List

# Add parent directory to path to allow running directly from this file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.extractor_agent import EntityExtractorAgent, RelationExtractorAgent
from agents.rdf_builder_agent import RDFBuilderAgent, GraphToolbox
from agents.validator_agent import ValidatorAgent
from agents.critic_agent import CriticAgent, CriticReport


class RootAgent:
    """Root Agent that orchestrates and routes tasks, implementing a generate -> validate -> critique -> correct loop."""
    
    def __init__(
        self,
        entity_extractor: EntityExtractorAgent,
        relation_extractor: RelationExtractorAgent,
        rdf_builder: RDFBuilderAgent,
        validator: ValidatorAgent,
        critic: CriticAgent
    ):
        self.entity_extractor = entity_extractor
        self.relation_extractor = relation_extractor
        self.rdf_builder = rdf_builder
        self.validator = validator
        self.critic = critic

    def run_pipeline(self, text: str, graph_id: str = "generated", max_loops: int = 2) -> Dict[str, Any]:
        """Orchestrate the multi-agent pipeline with critique and self-correction feedback loop."""
        # 1. Initialize local execution state (toolbox)
        toolbox = GraphToolbox()

        # 2. Extract Entities
        entity_result = self.entity_extractor.run(text)
        entities = entity_result.entities

        # 3. Extract Relations
        relation_result = self.relation_extractor.run(text, entities)
        relations = relation_result.relations

        feedback = []
        loop_history = []
        final_graph = None
        final_validation = None
        final_critic_report = None

        # 4. Generate -> Validate -> Critique -> Correct Loop
        for loop_idx in range(max_loops):
            iteration_name = f"Iteration {loop_idx + 1}"
            
            # Clear triples from previous iteration if graph exists to avoid duplicates
            if graph_id in toolbox.graphs:
                toolbox.graphs[graph_id].triples = []
            
            # A. Run builder (passing feedback if on loop > 0)
            builder_summary = self.rdf_builder.run(
                entities=entities,
                relations=relations,
                toolbox=toolbox,
                graph_id=graph_id,
                critic_feedback=feedback if loop_idx > 0 else None
            )

            # B. Get graph
            graph = toolbox.graphs.get(graph_id)
            if graph is None:
                toolbox.create_graph(graph_id)
                graph = toolbox.graphs[graph_id]
            
            final_graph = graph

            # C. Run Validator
            validation = self.validator.run(graph)
            final_validation = validation

            # D. Run Critic
            validation_errors_str = "; ".join([iss.message for iss in validation.issues]) if not validation.is_valid else "None"
            critic_report = self.critic.run(
                source_text=text,
                turtle_graph=graph.serialize("turtle"),
                validation_errors=validation_errors_str
            )
            final_critic_report = critic_report

            # Log this iteration's state
            loop_history.append({
                "iteration": iteration_name,
                "is_approved": critic_report.is_approved and validation.is_valid,
                "confidence": critic_report.overall_confidence,
                "validation_issues": [iss.model_dump() for iss in validation.issues],
                "critic_evaluations": [eval_item.model_dump() for eval_item in critic_report.evaluations],
                "critic_recommendations": [rec.model_dump() for rec in critic_report.recommendations],
                "turtle": graph.serialize("turtle")
            })

            # Check if we can approve and exit
            if critic_report.is_approved and validation.is_valid:
                toolbox.execution_log.append(f"🎉 Graph approved by Critic on {iteration_name}!")
                break
            
            # Prepare feedback recommendations for the next loop
            feedback = [rec.action for rec in critic_report.recommendations] + [iss.message for iss in validation.issues]
            toolbox.execution_log.append(f"🔄 Graph rejected on {iteration_name}. Sending feedback to Builder Agent for self-correction.")

        return {
            "entities": entities,
            "relations": relations,
            "execution_log": toolbox.execution_log,
            "loop_history": loop_history,
            "graph": final_graph,
            "validation": final_validation,
            "critic": final_critic_report,
            "turtle": final_graph.serialize("turtle")
        }


class RDFGraphWorkflow:
    """Orchestrator class wrapping the RootAgent for backward compatibility and server route integration."""
    
    def __init__(
        self,
        entity_extractor: EntityExtractorAgent,
        relation_extractor: RelationExtractorAgent,
        builder_agent: RDFBuilderAgent,
        validator_agent: ValidatorAgent,
        critic_agent: CriticAgent = None
    ):
        if critic_agent is None:
            critic_agent = CriticAgent()
            
        self.root_agent = RootAgent(
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
            rdf_builder=builder_agent,
            validator=validator_agent,
            critic=critic_agent
        )

    def run(self, text: str) -> Dict[str, Any]:
        result = self.root_agent.run_pipeline(text)
        # Re-structure for backward compatibility with UI expectations while adding new telemetry
        return {
            "extraction": {
                "entities": result["entities"],
                "relations": result["relations"]
            },
            "execution_log": result["execution_log"],
            "loop_history": result["loop_history"],
            "graph": result["graph"],
            "validation": result["validation"],
            "critic": result["critic"],
            "turtle": result["turtle"]
        }


if __name__ == "__main__":
    # Test workflow locally
    print("Initializing Root Agent and Sub-Agents (including Critic)...")
    entity_extractor = EntityExtractorAgent()
    relation_extractor = RelationExtractorAgent()
    builder = RDFBuilderAgent()
    validator = ValidatorAgent()
    critic = CriticAgent()

    workflow = RDFGraphWorkflow(
        entity_extractor=entity_extractor,
        relation_extractor=relation_extractor,
        builder_agent=builder,
        validator_agent=validator,
        critic_agent=critic
    )

    input_text = "Google was founded by Larry Page and Sergey Brin in 1998, and is headquartered in Mountain View."
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
        
    print("\n--- Loop History (Correction Steps) ---")
    for iteration in result["loop_history"]:
        print(f"📍 {iteration['iteration']}: Approved = {iteration['is_approved']}, Confidence = {iteration['confidence']}")
        if iteration["critic_recommendations"]:
            print("  Recommendations:")
            for rec in iteration["critic_recommendations"]:
                print(f"  - Issue: {rec['issue']} | Action: {rec['action']}")
                
    print("\n--- Final Critic Evaluation ---")
    print(result["critic"].model_dump_json(indent=2))
    
    print("\n--- Final Generated Turtle ---")
    print(result["turtle"])
