import rdflib
from typing import Tuple, Union, Optional
from app.models.rdf import (
    RDFGraph, RDFDataset, RDFTerm, IRINode, BlankNode, LiteralNode, RDFTriple, RDFQuad
)


def to_rdflib_node(node: RDFTerm) -> rdflib.term.Node:
    if isinstance(node, IRINode):
        return rdflib.URIRef(node.value)
    elif isinstance(node, BlankNode):
        return rdflib.BNode(node.value)
    elif isinstance(node, LiteralNode):
        # A Literal can only have one of lang or datatype in RDFLib
        if node.language:
            return rdflib.Literal(node.value, lang=node.language)
        return rdflib.Literal(node.value, datatype=node.datatype)
    else:
        raise ValueError(f"Unknown RDFTerm type: {type(node)}")


def from_rdflib_node(node: rdflib.term.Node) -> RDFTerm:
    if isinstance(node, rdflib.URIRef):
        return IRINode(str(node))
    elif isinstance(node, rdflib.BNode):
        return BlankNode(str(node))
    elif isinstance(node, rdflib.Literal):
        return LiteralNode(
            value=node.value if node.value is not None else str(node),
            datatype=str(node.datatype) if node.datatype else None,
            language=str(node.language) if node.language else None
        )
    else:
        raise TypeError(f"Unknown rdflib node type: {type(node)}")


def to_rdflib_triple(triple: RDFTriple) -> Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node]:
    return (
        to_rdflib_node(triple.subject),
        to_rdflib_node(triple.predicate),
        to_rdflib_node(triple.object)
    )


def from_rdflib_triple(triple_tuple: Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node]) -> RDFTriple:
    s, p, o = triple_tuple
    s_node = from_rdflib_node(s)
    p_node = from_rdflib_node(p)
    o_node = from_rdflib_node(o)
    if not isinstance(s_node, (IRINode, BlankNode)):
        raise ValueError("Subject of RDF triple must be an IRINode or BlankNode")
    if not isinstance(p_node, IRINode):
        raise ValueError("Predicate of RDF triple must be an IRINode")
    return RDFTriple(subject=s_node, predicate=p_node, object=o_node)


def to_rdflib_quad(quad: RDFQuad) -> Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node, Optional[rdflib.term.Node]]:
    return (
        to_rdflib_node(quad.subject),
        to_rdflib_node(quad.predicate),
        to_rdflib_node(quad.object),
        to_rdflib_node(quad.graph) if quad.graph is not None else None
    )


def from_rdflib_quad(quad_tuple: Tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node, Optional[rdflib.term.Node]]) -> RDFQuad:
    s, p, o, g = quad_tuple
    s_node = from_rdflib_node(s)
    p_node = from_rdflib_node(p)
    o_node = from_rdflib_node(o)
    
    if not isinstance(s_node, (IRINode, BlankNode)):
        raise ValueError("Subject of RDF quad must be an IRINode or BlankNode")
    if not isinstance(p_node, IRINode):
        raise ValueError("Predicate of RDF quad must be an IRINode")
        
    g_node = None
    if g is not None:
        g_str = str(g)
        if g_str != "urn:x-rdflib:default":
            g_node = from_rdflib_node(g)
            if not isinstance(g_node, (IRINode, BlankNode)):
                raise ValueError("Graph name must be an IRINode or BlankNode")
                
    return RDFQuad(subject=s_node, predicate=p_node, object=o_node, graph=g_node)


class RDFGraphService:
    def serialize(self, graph: RDFGraph, format: str) -> str:
        """Convert a Pydantic RDFGraph to an RDFLib graph and serialize it to the target format."""
        g = rdflib.Graph()
        
        # Bind registered namespaces to RDFLib Graph
        for prefix, uri in graph.namespaces.items():
            g.bind(prefix, rdflib.Namespace(uri))
            
        for t in graph.triples:
            s_ref = to_rdflib_node(t.subject)
            p_ref = to_rdflib_node(t.predicate)
            o_ref = to_rdflib_node(t.object)
            g.add((s_ref, p_ref, o_ref))
            
        res_bytes = g.serialize(format=format)
        if isinstance(res_bytes, bytes):
            return res_bytes.decode("utf-8")
        return res_bytes

    def from_rdflib_graph(self, g: rdflib.Graph, graph_id: str = "default") -> RDFGraph:
        """Convert an RDFLib Graph to our Pydantic RDFGraph."""
        triples = []
        for t in g:
            triples.append(from_rdflib_triple(t))
        return RDFGraph(graph_id=graph_id, triples=triples)


class RDFDatasetService:
    def serialize(self, dataset: RDFDataset, format: str) -> str:
        """Convert a Pydantic RDFDataset to an RDFLib Dataset and serialize it."""
        d = rdflib.Dataset()
        
        # Bind registered namespaces
        for prefix, uri in dataset.namespaces.items():
            d.bind(prefix, rdflib.Namespace(uri))
            
        for q in dataset.quads:
            s_ref = to_rdflib_node(q.subject)
            p_ref = to_rdflib_node(q.predicate)
            o_ref = to_rdflib_node(q.object)
            g_ref = to_rdflib_node(q.graph) if q.graph is not None else rdflib.URIRef("urn:x-rdflib:default")
            d.add((s_ref, p_ref, o_ref, g_ref))
            
        res_bytes = d.serialize(format=format)
        if isinstance(res_bytes, bytes):
            return res_bytes.decode("utf-8")
        return res_bytes

    def from_rdflib_dataset(self, d: rdflib.Dataset) -> RDFDataset:
        """Convert an RDFLib Dataset to our Pydantic RDFDataset."""
        dataset = RDFDataset()
        for prefix, uri in d.namespaces():
            dataset.bind(prefix, str(uri))

        for s, p, o, g in d.quads((None, None, None, None)):
            graph_name = "default"
            if g is not None:
                g_str = str(g)
                if g_str != "urn:x-rdflib:default":
                    graph_name = g_str
            
            graph = dataset.graph(graph_name)
            graph.add(from_rdflib_node(s), from_rdflib_node(p), from_rdflib_node(o))
            
        return dataset
