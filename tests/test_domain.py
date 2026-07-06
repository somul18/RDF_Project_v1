import pytest
from app.models.rdf import (
    RDFGraph, RDFDataset, IRINode, BlankNode, LiteralNode, RDFTriple, RDFQuad
)


def test_rdf_graph_namespaces_and_expansion():
    g = RDFGraph(graph_id="test")
    g.bind("ex", "http://example.org/")
    
    # Check manual expansion
    assert g.expand_prefix("ex:foo") == "http://example.org/foo"
    assert g.expand_prefix("unbound:foo") == "unbound:foo"
    
    # Check expansion during add
    g.add("ex:s", "ex:p", "ex:o")
    assert g.triples[0].subject == IRINode("http://example.org/s")
    assert g.triples[0].predicate == IRINode("http://example.org/p")
    assert g.triples[0].object == IRINode("http://example.org/o")


def test_rdf_graph_add_convenience_methods():
    g = RDFGraph(graph_id="test")
    g.bind("ex", "http://example.org/")
    g.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    g.add_type("ex:Marie_Curie", "ex:Person")
    g.add_literal("ex:Marie_Curie", "ex:birthYear", 1867)

    assert len(g.triples) == 2
    
    # Assert type triple
    t_type = g.triples[0]
    assert t_type.subject == IRINode("http://example.org/Marie_Curie")
    assert t_type.predicate == IRINode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    assert t_type.object == IRINode("http://example.org/Person")

    # Assert literal triple
    t_lit = g.triples[1]
    assert t_lit.subject == IRINode("http://example.org/Marie_Curie")
    assert t_lit.predicate == IRINode("http://example.org/birthYear")
    assert t_lit.object == LiteralNode(1867)


def test_rdf_graph_query_and_mutation():
    g = RDFGraph(graph_id="test")
    g.bind("ex", "http://example.org/")
    
    g.add("ex:s1", "ex:p1", "ex:o1")
    g.add("ex:s1", "ex:p2", "ex:o2")
    g.add("ex:s2", "ex:p1", "ex:o3")
    
    # Contains
    assert g.contains("ex:s1", "ex:p1", "ex:o1")
    assert not g.contains("ex:s1", "ex:p1", "ex:o2")
    
    # Find
    assert len(g.find("ex:s1")) == 2
    assert len(g.find(None, "ex:p1")) == 2
    assert len(g.find(None, None, "ex:o2")) == 1
    
    # Subjects, Predicates, Objects
    assert set(g.subjects()) == {IRINode("http://example.org/s1"), IRINode("http://example.org/s2")}
    assert set(g.predicates()) == {IRINode("http://example.org/p1"), IRINode("http://example.org/p2")}
    assert set(g.objects()) == {
        IRINode("http://example.org/o1"),
        IRINode("http://example.org/o2"),
        IRINode("http://example.org/o3")
    }
    
    # Remove
    g.remove(None, "ex:p1", None)
    assert len(g.triples) == 1
    assert g.triples[0].predicate == IRINode("http://example.org/p2")
