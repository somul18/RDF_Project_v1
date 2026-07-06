from typing import List
from pydantic import BaseModel, Field
from app.models.rdf import RDFGraph, IRINode, BlankNode, LiteralNode


class ValidationIssue(BaseModel):
    triple: str = Field(..., description="String representation of the triple containing the issue")
    rule: str = Field(..., description="Name of the validation rule violated")
    severity: str = Field(..., description="Severity of the issue: 'error' or 'warning'")
    message: str = Field(..., description="Description of the validation issue")


class ValidationReport(BaseModel):
    is_valid: bool = Field(..., description="True if there are no errors, False otherwise")
    issues: List[ValidationIssue] = Field(default_factory=list)


class ValidatorAgent:
    def run(self, graph: RDFGraph) -> ValidationReport:
        """Validate the triples in an RDFGraph according to syntactic and semantic constraints."""
        issues = []
        seen_triples = set()

        for t in graph.triples:
            triple_str = f"({t.subject.value}, {t.predicate.value}, {t.object.value})"
            
            # Rule 1: Validate Subject Type (must be IRINode or BlankNode)
            if not isinstance(t.subject, (IRINode, BlankNode)):
                issues.append(
                    ValidationIssue(
                        triple=triple_str,
                        rule="SubjectType",
                        severity="error",
                        message=f"Subject must be an IRI or BlankNode, got {type(t.subject).__name__}"
                    )
                )

            # Rule 2: Validate Predicate Type (must be IRINode)
            if not isinstance(t.predicate, IRINode):
                issues.append(
                    ValidationIssue(
                        triple=triple_str,
                        rule="PredicateType",
                        severity="error",
                        message=f"Predicate must be an IRI, got {type(t.predicate).__name__}"
                    )
                )

            # Rule 3: Validate Prefix bindings
            for node in (t.subject, t.predicate, t.object):
                if isinstance(node, IRINode) and ":" in node.value:
                    # Check if it starts with http/https - if so, it's absolute, no expansion needed
                    if node.value.startswith("http://") or node.value.startswith("https://"):
                        continue
                    prefix, local = node.value.split(":", 1)
                    if prefix not in graph.namespaces:
                        issues.append(
                            ValidationIssue(
                                triple=triple_str,
                                rule="UnboundPrefix",
                                severity="error",
                                message=f"Unbound prefix '{prefix}' used in URI '{node.value}'"
                            )
                        )

            # Rule 4: Duplicate triple check
            t_hash = (t.subject, t.predicate, t.object)
            if t_hash in seen_triples:
                issues.append(
                    ValidationIssue(
                        triple=triple_str,
                        rule="DuplicateTriple",
                        severity="warning",
                        message="Duplicate triple detected in graph"
                    )
                )
            else:
                seen_triples.add(t_hash)

        # Check if there are any error severity issues
        is_valid = not any(issue.severity == "error" for issue in issues)
        
        return ValidationReport(is_valid=is_valid, issues=issues)
