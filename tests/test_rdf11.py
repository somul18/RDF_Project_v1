import pytest
from rdf11.model import IRI, BlankNode, Literal, Triple, Graph, Quad, Dataset, ANY
from rdf11.parser import parse_n_triples, parse_n_quads
from rdf11.serializer import serialize_n_triples, serialize_n_quads
from rdf11.isomorphism import are_graphs_isomorphic, are_datasets_isomorphic

# =====================================================================
# Test RDF Terms
# =====================================================================

def test_iri_valid():
    iri = IRI("http://example.org/foo")
    assert iri.value == "http://example.org/foo"
    assert iri.n3() == "<http://example.org/foo>"
    assert repr(iri) == "<http://example.org/foo>"

    # Other schemes
    assert IRI("urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6").value == "urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
    assert IRI("mailto:alice@example.com").value == "mailto:alice@example.com"


def test_iri_invalid():
    # Relative URI is not allowed
    with pytest.raises(ValueError, match="must be absolute"):
        IRI("foo/bar")
    with pytest.raises(ValueError, match="must be absolute"):
        IRI("/foo/bar")
    with pytest.raises(TypeError):
        IRI(123)


def test_iri_equality():
    iri1 = IRI("http://example.org/foo")
    iri2 = IRI("http://example.org/foo")
    iri3 = IRI("http://example.org/bar")
    assert iri1 == iri2
    assert iri1 != iri3
    assert hash(iri1) == hash(iri2)
    assert hash(iri1) != hash(iri3)


def test_blank_node_creation():
    b1 = BlankNode()
    assert b1.value.startswith("b")
    assert len(b1.value) > 1
    
    b2 = BlankNode("foo")
    assert b2.value == "foo"
    assert b2.n3() == "_:foo"
    
    # Strip _:
    b3 = BlankNode("_:bar")
    assert b3.value == "bar"
    assert b3.n3() == "_:bar"


def test_blank_node_invalid():
    with pytest.raises(ValueError, match="cannot be empty"):
        BlankNode("")
    with pytest.raises(ValueError, match="cannot be empty"):
        BlankNode("_:")
    with pytest.raises(TypeError):
        BlankNode(123)


def test_blank_node_equality():
    b1 = BlankNode("foo")
    b2 = BlankNode("_:foo")
    b3 = BlankNode("bar")
    assert b1 == b2
    assert b1 != b3
    assert hash(b1) == hash(b2)
    assert hash(b1) != hash(b3)


def test_literal_creation():
    # Simple literal
    lit1 = Literal("hello")
    assert lit1.value == "hello"
    assert lit1.datatype == IRI("http://www.w3.org/2001/XMLSchema#string")
    assert lit1.language is None
    assert lit1.is_simple
    assert lit1.n3() == '"hello"'
    
    # Typed literal
    integer_datatype = IRI("http://www.w3.org/2001/XMLSchema#integer")
    lit2 = Literal("42", datatype=integer_datatype)
    assert lit2.value == "42"
    assert lit2.datatype == integer_datatype
    assert lit2.language is None
    assert not lit2.is_simple
    assert lit2.n3() == '"42"^^<http://www.w3.org/2001/XMLSchema#integer>'
    
    # Language-tagged literal
    lit3 = Literal("bonjour", language="FR")
    assert lit3.value == "bonjour"
    # Datatype should be rdf:langString
    assert lit3.datatype == IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")
    # Language tag must be canonicalized to lower case
    assert lit3.language == "fr"
    assert not lit3.is_simple
    assert lit3.n3() == '"bonjour"@fr'


def test_literal_validation():
    # Cannot have langString datatype without language tag
    with pytest.raises(ValueError, match="only allowed if a language tag is provided"):
        Literal("hello", datatype=IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"))
        
    # Cannot specify language tag with a datatype other than rdf:langString
    with pytest.raises(ValueError, match="Datatype must be"):
        Literal("hello", datatype=IRI("http://www.w3.org/2001/XMLSchema#string"), language="en")
        
    # Language tag must be non-empty
    with pytest.raises(ValueError, match="cannot be empty"):
        Literal("hello", language="")
        
    # Invalid language tag under BCP 47 (e.g. contains invalid characters or structure)
    with pytest.raises(ValueError, match="Invalid language tag"):
        Literal("hello", language="123456789")  # Subtags cannot exceed 8 chars, language must start with alpha
        
    with pytest.raises(ValueError, match="Invalid language tag"):
        Literal("hello", language="a")  # Primary language subtag must be 2-8 chars (except registered/grandfathered)


def test_literal_escapes_n3():
    # String containing double quote, backslash, newline, carriage return, tab, backspace, formfeed
    lit = Literal('Quote: ", Backslash: \\, Newline: \n, CR: \r, Tab: \t, BS: \b, FF: \f')
    assert lit.n3() == '"Quote: \\", Backslash: \\\\, Newline: \\n, CR: \\r, Tab: \\t, BS: \\b, FF: \\f"'


def test_literal_equality():
    lit1 = Literal("hello")
    lit2 = Literal("hello", datatype=IRI("http://www.w3.org/2001/XMLSchema#string"))
    lit3 = Literal("hello", language="en")
    lit4 = Literal("hello", language="EN")  # Canonicalization handles case
    lit5 = Literal("hello", language="en-US")
    lit6 = Literal("hello", datatype=IRI("http://www.w3.org/2001/XMLSchema#normalizedString"))
    
    assert lit1 == lit2
    assert lit3 == lit4
    assert lit1 != lit3
    assert lit3 != lit5
    assert lit1 != lit6
    assert hash(lit1) == hash(lit2)
    assert hash(lit3) == hash(lit4)
    assert hash(lit1) != hash(lit3)


# =====================================================================
# Test Triple and Quad
# =====================================================================

def test_triple_creation():
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = Literal("o")
    t = Triple(s, p, o)
    assert t.subject == s
    assert t.predicate == p
    assert t.object == o
    assert t.to_tuple() == (s, p, o)
    assert repr(t) == "Triple(<http://example.org/s>, <http://example.org/p>, \"o\")"

    # Invalid types
    with pytest.raises(TypeError):
        Triple(Literal("invalid_subject"), p, o)
    with pytest.raises(TypeError):
        Triple(s, BlankNode("invalid_predicate"), o)
    with pytest.raises(TypeError):
        Triple(s, p, 123)


def test_quad_creation():
    s = BlankNode("s")
    p = IRI("http://example.org/p")
    o = IRI("http://example.org/o")
    g = IRI("http://example.org/g")
    
    q1 = Quad(s, p, o, g)
    assert q1.subject == s
    assert q1.predicate == p
    assert q1.object == o
    assert q1.graph_name == g
    assert q1.to_triple() == Triple(s, p, o)
    assert repr(q1) == "Quad(_:s, <http://example.org/p>, <http://example.org/o>, <http://example.org/g>)"
    
    # Quad with default graph (None)
    q2 = Quad(s, p, o, None)
    assert q2.graph_name is None


# =====================================================================
# Test Graph
# =====================================================================

def test_graph_operations():
    s = IRI("http://example.org/s")
    p1 = IRI("http://example.org/p1")
    p2 = IRI("http://example.org/p2")
    o1 = Literal("val1")
    o2 = Literal("val2")
    
    t1 = Triple(s, p1, o1)
    t2 = Triple(s, p2, o2)
    
    g = Graph()
    assert len(g) == 0
    
    g.add(t1)
    assert len(g) == 1
    assert t1 in g
    assert t2 not in g
    
    g.add(t2)
    assert len(g) == 2
    assert t2 in g
    
    # Remove
    g.remove(t1)
    assert len(g) == 1
    assert t1 not in g
    assert t2 in g
    
    # Discard non-existent doesn't raise error
    g.remove(t1)
    
    # Reset and query
    g.add(t1)
    
    triples = list(g.triples(s=s))
    assert len(triples) == 2
    assert t1 in triples and t2 in triples
    
    assert list(g.triples(p=p1)) == [t1]
    assert list(g.triples(o=o2)) == [t2]
    assert list(g.triples(s=IRI("http://example.org/other"))) == []
    
    # Generators
    assert list(g.subjects()) == [s]
    assert set(g.predicates()) == {p1, p2}
    assert set(g.objects()) == {o1, o2}


def test_graph_set_operations():
    t1 = Triple(IRI("http://example.org/s"), IRI("http://example.org/p"), Literal("1"))
    t2 = Triple(IRI("http://example.org/s"), IRI("http://example.org/p"), Literal("2"))
    t3 = Triple(IRI("http://example.org/s"), IRI("http://example.org/p"), Literal("3"))
    
    g1 = Graph([t1, t2])
    g2 = Graph([t2, t3])
    
    # Union
    union_g = g1 | g2
    assert len(union_g) == 3
    assert t1 in union_g and t2 in union_g and t3 in union_g
    
    # Intersection
    inter_g = g1 & g2
    assert len(inter_g) == 1
    assert t2 in inter_g
    
    # Difference
    diff_g = g1 - g2
    assert len(diff_g) == 1
    assert t1 in diff_g


# =====================================================================
# Test Dataset
# =====================================================================

def test_dataset_operations():
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = Literal("val")
    g_name = IRI("http://example.org/graph")
    
    q_default = Quad(s, p, o, None)
    q_named = Quad(s, p, o, g_name)
    
    d = Dataset()
    assert len(d) == 0
    
    d.add(q_default)
    assert len(d) == 1
    assert q_default in d
    assert len(d.default_graph) == 1
    
    d.add(q_named)
    assert len(d) == 2
    assert q_named in d
    assert len(d.get_graph(g_name)) == 1
    
    # Iteration
    quads = list(d)
    assert len(quads) == 2
    assert q_default in quads and q_named in quads
    
    # Quads query pattern
    assert list(d.quads(g=None)) == [q_default]
    assert list(d.quads(g=g_name)) == [q_named]
    assert len(list(d.quads(g=ANY))) == 2
    assert len(list(d.quads(s=s, g=ANY))) == 2
    assert len(list(d.quads(o=Literal("non-existent"), g=ANY))) == 0
    
    # Graph names
    assert list(d.graph_names()) == [g_name]
    
    # Add named graph
    g_new_name = IRI("http://example.org/graph2")
    new_graph = Graph([Triple(s, p, Literal("other"))])
    d.add_graph(g_new_name, new_graph)
    assert len(d) == 3
    assert len(d.get_graph(g_new_name)) == 1
    
    # Remove graph
    d.remove_graph(g_new_name)
    assert len(d) == 2
    assert g_new_name not in list(d.graph_names())


# =====================================================================
# Test N-Triples & N-Quads Parsers
# =====================================================================

def test_parse_n_triples():
    nt_data = """
    # This is a comment line
    <http://example.org/s> <http://example.org/p> <http://example.org/o> .
    
    _:b1 <http://example.org/p> "Hello World" . # inline comment
    _:b1 <http://example.org/p> "Hello \\"Quotes\\" and \\\\ backslash" .
    <http://example.org/s> <http://example.org/p> "Bonjour"@fr .
    <http://example.org/s> <http://example.org/p> "42"^^<http://www.w3.org/2001/XMLSchema#integer> .
    """
    g = parse_n_triples(nt_data)
    assert len(g) == 5
    
    # Verify IRI subject, predicate, object
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = IRI("http://example.org/o")
    assert Triple(s, p, o) in g
    
    # Verify simple string literal with backslash and quotes escaping
    b1_triples = list(g.triples(p=p, o=Literal('Hello "Quotes" and \\ backslash')))
    assert len(b1_triples) == 1
    assert isinstance(b1_triples[0].subject, BlankNode)
    
    # Verify language-tagged literal
    assert Triple(s, p, Literal("Bonjour", language="fr")) in g
    
    # Verify datatyped literal
    integer_datatype = IRI("http://www.w3.org/2001/XMLSchema#integer")
    assert Triple(s, p, Literal("42", datatype=integer_datatype)) in g


def test_parse_n_triples_escaped_unicode():
    nt_data = r'<http://example.org/s> <http://example.org/p> "Unicode: \u263A \U0001F600" .'
    g = parse_n_triples(nt_data)
    assert len(g) == 1
    t = list(g)[0]
    assert t.object.value == "Unicode: ☺ 😀"


def test_parse_n_triples_invalid():
    # Missing dot
    with pytest.raises(ValueError, match="Expected '.'"):
        parse_n_triples('<http://example.org/s> <http://example.org/p> <http://example.org/o>')
        
    # Invalid character in IRI
    with pytest.raises(ValueError, match="Invalid character in IRI"):
        parse_n_triples('<http://example.org/s s> <http://example.org/p> <http://example.org/o> .')


def test_parse_n_quads():
    nq_data = """
    <http://example.org/s> <http://example.org/p> <http://example.org/o> . # Default graph
    <http://example.org/s> <http://example.org/p> <http://example.org/o> <http://example.org/g> . # Named graph IRI
    <http://example.org/s> <http://example.org/p> <http://example.org/o> _:bgraph . # Named graph Blank Node
    """
    d = parse_n_quads(nq_data)
    assert len(d) == 3
    
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = IRI("http://example.org/o")
    g = IRI("http://example.org/g")
    
    assert Quad(s, p, o, None) in d
    assert Quad(s, p, o, g) in d
    
    # Find blank node named graph quad
    named_bn_quads = list(d.quads(g=ANY))
    bn_graph_quad = [q for q in named_bn_quads if isinstance(q.graph_name, BlankNode)]
    assert len(bn_graph_quad) == 1
    assert bn_graph_quad[0].graph_name.value == "bgraph"


# =====================================================================
# Test Serializers
# =====================================================================

def test_serialize_n_triples():
    g = Graph()
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = Literal("hello \n world")
    g.add(Triple(s, p, o))
    g.add(Triple(s, p, IRI("http://example.org/o")))
    
    serialized = serialize_n_triples(g)
    expected = (
        '<http://example.org/s> <http://example.org/p> "hello \\n world" .\n'
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n"
    )
    assert serialized == expected


def test_serialize_n_quads():
    d = Dataset()
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = IRI("http://example.org/o")
    g = IRI("http://example.org/g")
    
    d.add(Quad(s, p, o, None))
    d.add(Quad(s, p, o, g))
    
    serialized = serialize_n_quads(d)
    expected = (
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n"
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> <http://example.org/g> .\n"
    )
    assert serialized == expected


# =====================================================================
# Test Isomorphism
# =====================================================================

def test_graph_isomorphism():
    # Example 1: Empty graphs
    assert are_graphs_isomorphic(Graph(), Graph())
    
    # Example 2: Simple isomorphic graphs with different bnode labels
    t1_a = Triple(BlankNode("a"), IRI("http://example.org/p"), Literal("val"))
    t1_b = Triple(BlankNode("a"), IRI("http://example.org/p2"), BlankNode("b"))
    t1_c = Triple(BlankNode("b"), IRI("http://example.org/p3"), IRI("http://example.org/o"))
    g1 = Graph([t1_a, t1_b, t1_c])
    
    t2_a = Triple(BlankNode("x"), IRI("http://example.org/p"), Literal("val"))
    t2_b = Triple(BlankNode("x"), IRI("http://example.org/p2"), BlankNode("y"))
    t2_c = Triple(BlankNode("y"), IRI("http://example.org/p3"), IRI("http://example.org/o"))
    g2 = Graph([t2_a, t2_b, t2_c])
    
    assert are_graphs_isomorphic(g1, g2)
    
    # Example 3: Non-isomorphic due to edge mismatch
    t3_b = Triple(BlankNode("x"), IRI("http://example.org/p_wrong"), BlankNode("y"))
    g3 = Graph([t2_a, t3_b, t2_c])
    assert not are_graphs_isomorphic(g1, g3)
    
    # Example 4: Non-isomorphic due to structure mismatch (cycle vs path)
    # Graph A: b1 -> b2 -> b3 -> b1 (cycle)
    # Graph B: b1 -> b2 -> b3 -> b4 (path)
    p = IRI("http://example.org/next")
    ga = Graph([
        Triple(BlankNode("1"), p, BlankNode("2")),
        Triple(BlankNode("2"), p, BlankNode("3")),
        Triple(BlankNode("3"), p, BlankNode("1"))
    ])
    gb = Graph([
        Triple(BlankNode("1"), p, BlankNode("2")),
        Triple(BlankNode("2"), p, BlankNode("3")),
        Triple(BlankNode("3"), p, BlankNode("4"))
    ])
    assert not are_graphs_isomorphic(ga, gb)


def test_dataset_isomorphism():
    d1 = Dataset()
    d2 = Dataset()
    
    s = IRI("http://example.org/s")
    p = IRI("http://example.org/p")
    o = IRI("http://example.org/o")
    
    b1 = BlankNode("b1")
    b2 = BlankNode("b2")
    
    # Default graph triples
    d1.add(Quad(b1, p, o, None))
    d1.add(Quad(s, p, b1, b2))  # Shared blank node b1 in named graph named b2
    
    bx = BlankNode("bx")
    by = BlankNode("by")
    d2.add(Quad(bx, p, o, None))
    d2.add(Quad(s, p, bx, by))
    
    assert are_datasets_isomorphic(d1, d2)
    
    # Mismatch (graph name doesn't match)
    d3 = Dataset()
    d3.add(Quad(bx, p, o, None))
    d3.add(Quad(s, p, bx, IRI("http://example.org/fixed")))
    assert not are_datasets_isomorphic(d1, d3)
