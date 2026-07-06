import rdflib
from typing import Union, Optional, List, Tuple
from pydantic import BaseModel, Field, model_validator


class RDFNode(BaseModel):
    """Represent an RDF URI or Blank Node, or base for RDFLiteral."""
    type: str = Field(..., description="Node type: 'uri', 'bnode', or 'literal'")
    value: str = Field(..., description="Lexical value or identifier of the node")

    def to_rdflib(self) -> rdflib.term.Node:
        if self.type == "uri":
            return rdflib.URIRef(self.value)
        elif self.type == "bnode":
            return rdflib.BNode(self.value)
        elif self.type == "literal":
            # If instantiated as base class but representing a literal
            dt = getattr(self, "datatype", None)
            lang = getattr(self, "language", None)
            return rdflib.Literal(self.value, datatype=dt, lang=lang)
        else:
            raise ValueError(f"Unknown RDFNode type: {self.type}")

    @classmethod
    def from_rdflib(cls, node: rdflib.term.Node) -> Union["RDFNode", "RDFLiteral"]:
        if isinstance(node, rdflib.URIRef):
            return cls(type="uri", value=str(node))
        elif isinstance(node, rdflib.BNode):
            return cls(type="bnode", value=str(node))
        elif isinstance(node, rdflib.Literal):
            return RDFLiteral(
                value=str(node),
                datatype=str(node.datatype) if node.datatype else None,
                language=str(node.language) if node.language else None
            )
        else:
            raise TypeError(f"Unsupported RDFLib node: {type(node)}")


class RDFLiteral(RDFNode):
    """Represent an RDF Literal with optional datatype and language tag."""
    type: str = Field("literal", description="Must be 'literal'")
    datatype: Optional[str] = Field(None, description="Datatype URI")
    language: Optional[str] = Field(None, description="Language tag")

    def to_rdflib(self) -> rdflib.Literal:
        # In rdflib, Literal constructor takes lang (not language)
        return rdflib.Literal(self.value, datatype=self.datatype, lang=self.language)


class RDFTriple(BaseModel):
    """Represent an RDF Triple (subject, predicate, object)."""
    subject: RDFNode
    predicate: RDFNode
    object: Union[RDFLiteral, RDFNode]

    @model_validator(mode="after")
    def validate_triple_types(self) -> "RDFTriple":
        # Subject must be URI or BlankNode
        if self.subject.type not in ("uri", "bnode"):
            raise ValueError("Subject of RDF triple must be a URI or a Blank Node")
        # Predicate must be a URI
        if self.predicate.type != "uri":
            raise ValueError("Predicate of RDF triple must be a URI")
        return self

    def to_rdflib(self) -> Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node]:
        return (
            self.subject.to_rdflib(),
            self.predicate.to_rdflib(),
            self.object.to_rdflib()
        )

    @classmethod
    def from_rdflib(cls, triple: Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node]) -> "RDFTriple":
        s, p, o = triple
        
        # subject must be uri or bnode
        s_node = RDFNode.from_rdflib(s)
        if isinstance(s_node, RDFLiteral):
            raise ValueError("Subject of RDF triple cannot be a literal")
            
        p_node = RDFNode.from_rdflib(p)
        if isinstance(p_node, RDFLiteral) or p_node.type != "uri":
            raise ValueError("Predicate of RDF triple must be a URI")
            
        o_node = RDFNode.from_rdflib(o)
        
        return cls(subject=s_node, predicate=p_node, object=o_node)


class RDFGraph(BaseModel):
    """Represent an RDF Graph as a collection of RDFTriples."""
    triples: List[RDFTriple]

    def to_rdflib(self) -> rdflib.Graph:
        g = rdflib.Graph()
        for t in self.triples:
            g.add(t.to_rdflib())
        return g

    @classmethod
    def from_rdflib(cls, graph: rdflib.Graph) -> "RDFGraph":
        triples_list = []
        for t in graph:
            triples_list.append(RDFTriple.from_rdflib(t))
        return cls(triples=triples_list)


class RDFQuad(BaseModel):
    """Represent an RDF Quad (subject, predicate, object, graph)."""
    subject: RDFNode
    predicate: RDFNode
    object: Union[RDFLiteral, RDFNode]
    graph: Optional[RDFNode] = None

    @model_validator(mode="after")
    def validate_quad_types(self) -> "RDFQuad":
        if self.subject.type not in ("uri", "bnode"):
            raise ValueError("Subject of RDF quad must be a URI or a Blank Node")
        if self.predicate.type != "uri":
            raise ValueError("Predicate of RDF quad must be a URI")
        if self.graph is not None and self.graph.type not in ("uri", "bnode"):
            raise ValueError("Graph name of RDF quad must be a URI or a Blank Node")
        return self

    def to_rdflib(self) -> Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node, Optional[rdflib.term.Node]]:
        return (
            self.subject.to_rdflib(),
            self.predicate.to_rdflib(),
            self.object.to_rdflib(),
            self.graph.to_rdflib() if self.graph is not None else None
        )

    @classmethod
    def from_rdflib(cls, quad: Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node, Optional[rdflib.term.Node]]) -> "RDFQuad":
        s, p, o, g = quad
        s_node = RDFNode.from_rdflib(s)
        if isinstance(s_node, RDFLiteral):
            raise ValueError("Subject of RDF quad cannot be a literal")
            
        p_node = RDFNode.from_rdflib(p)
        if isinstance(p_node, RDFLiteral) or p_node.type != "uri":
            raise ValueError("Predicate of RDF quad must be a URI")
            
        o_node = RDFNode.from_rdflib(o)
        
        g_node = None
        if g is not None:
            g_str = str(g)
            if g_str != "urn:x-rdflib:default":
                g_node = RDFNode.from_rdflib(g)
                if isinstance(g_node, RDFLiteral):
                    raise ValueError("Graph name cannot be a literal")
                
        return cls(subject=s_node, predicate=p_node, object=o_node, graph=g_node)


class RDFDataset(BaseModel):
    """Represent an RDF Dataset as a collection of RDFQuads."""
    quads: List[RDFQuad]

    def to_rdflib(self) -> rdflib.Dataset:
        d = rdflib.Dataset()
        for q in self.quads:
            s, p, o, g = q.to_rdflib()
            g_ref = g if g is not None else rdflib.URIRef("urn:x-rdflib:default")
            d.add((s, p, o, g_ref))
        return d

    @classmethod
    def from_rdflib(cls, dataset: rdflib.Dataset) -> "RDFDataset":
        quads_list = []
        for s, p, o, g in dataset.quads((None, None, None, None)):
            quads_list.append(RDFQuad.from_rdflib((s, p, o, g)))
        return cls(quads=quads_list)
