import pytest
from fastapi.testclient import TestClient

from app.models.rdf import (
    IRINode, BlankNode, LiteralNode, RDFTriple, RDFQuad, RDFDataset, RDFGraph
)
from app.services.rdf_service import (
    to_rdflib_node, from_rdflib_node,
    to_rdflib_triple, from_rdflib_triple,
    to_rdflib_quad, from_rdflib_quad
)
from entrypoint.server import app

client = TestClient(app)

# =====================================================================
# Test JSON & RDFLib Conversion
# =====================================================================

def test_term_json_conversion():
    # Test IRI
    iri = IRINode("http://example.org/foo")
    assert iri.value == "http://example.org/foo"
    # Validate to/from rdflib
    rl_iri = to_rdflib_node(iri)
    assert str(rl_iri) == "http://example.org/foo"
    assert from_rdflib_node(rl_iri) == iri

    # Test BlankNode
    bn = BlankNode("b1")
    assert bn.value == "b1"
    rl_bn = to_rdflib_node(bn)
    assert str(rl_bn) == "b1"
    assert from_rdflib_node(rl_bn) == bn

    # Test LiteralNode
    lit = LiteralNode(42)
    assert lit.value == 42
    rl_lit = to_rdflib_node(lit)
    assert rl_lit.value == 42
    assert from_rdflib_node(rl_lit).value == lit.value


# =====================================================================
# Test HTTP Endpoints
# =====================================================================

@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    # Clear the database before each test
    client.post("/clear")
    yield


def test_clear_endpoint():
    # Add a quad first
    q = {
        "subject": {"type": "uri", "value": "http://example.org/s"},
        "predicate": {"type": "uri", "value": "http://example.org/p"},
        "object": {"type": "literal", "value": "val"},
        "graph": None
    }
    client.post("/quads", json=q)
    
    # Query should show 1 quad
    res = client.get("/quads")
    assert len(res.json()["quads"]) == 1
    
    # Clear
    clear_res = client.post("/clear")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "success"
    
    # Query should show 0 quads
    res_empty = client.get("/quads")
    assert len(res_empty.json()["quads"]) == 0


def test_parse_ntriples_endpoint():
    nt_data = '<http://example.org/s> <http://example.org/p> <http://example.org/o> .'
    res = client.post("/parse", json={
        "content": nt_data,
        "format": "ntriples"
    })
    assert res.status_code == 200
    assert len(res.json()["triples"]) == 1

    # Check that it exists in default graph
    q_res = client.get("/quads", params={"match_all_graphs": False})
    assert len(q_res.json()["quads"]) == 1
    
    # Parse to specific named graph
    res2 = client.post("/parse", json={
        "content": nt_data,
        "format": "ntriples",
        "graph": "<http://example.org/g1>"
    })
    assert res2.status_code == 200
    assert len(res2.json()["triples"]) == 1

    # Query named graph specifically
    q_res2 = client.get("/quads", params={"g": "<http://example.org/g1>"})
    assert len(q_res2.json()["quads"]) == 1


def test_parse_nquads_endpoint():
    nq_data = (
        '<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n'
        '<http://example.org/s> <http://example.org/p> <http://example.org/o> <http://example.org/g2> .'
    )
    res = client.post("/parse", json={
        "content": nq_data,
        "format": "nquads"
    })
    assert res.status_code == 200
    assert len(res.json()["quads"]) == 2

    # Query all
    q_all = client.get("/quads", params={"match_all_graphs": True})
    assert len(q_all.json()["quads"]) == 2


def test_add_and_delete_quads_endpoints():
    q_data = {
        "subject": {"type": "uri", "value": "http://example.org/s"},
        "predicate": {"type": "uri", "value": "http://example.org/p"},
        "object": {"type": "literal", "value": "test_val", "language": "en"},
        "graph": {"type": "uri", "value": "http://example.org/g"}
    }
    # Add
    res = client.post("/quads", json=q_data)
    assert res.status_code == 201
    assert res.json()["status"] == "success"

    # Query matching predicate and lang tag
    q_res = client.get("/quads", params={"p": "<http://example.org/p>", "o": '"test_val"@en'})
    assert len(q_res.json()["quads"]) == 1

    # Delete
    del_res = client.delete("/quads", params={"o": '"test_val"@en'})
    assert del_res.status_code == 200
    assert del_res.json()["quads_removed"] == 1

    # Verify deleted
    assert len(client.get("/quads").json()["quads"]) == 0


def test_serialize_endpoint():
    # Setup some data
    client.post("/parse", json={
        "content": '<http://example.org/s> <http://example.org/p> "hello" .',
        "format": "ntriples"
    })
    
    # Serialize N-Triples
    res = client.get("/serialize", params={"format": "ntriples"})
    assert res.status_code == 200
    # RDFLib serialization could have spaces or slight differences, but it will contain the triple base
    assert '<http://example.org/s> <http://example.org/p> "hello"' in res.text
    
    # Serialize N-Quads
    res_nq = client.get("/serialize", params={"format": "nquads"})
    assert res_nq.status_code == 200
    assert '<http://example.org/s> <http://example.org/p> "hello"' in res_nq.text


def test_isomorphism_endpoints():
    # Graph Isomorphism
    req_g = {
        "graph1": "_:b1 <http://example.org/p> <http://example.org/o> .",
        "graph2": "_:b2 <http://example.org/p> <http://example.org/o> ."
    }
    res_g = client.post("/isomorphic/graphs", json=req_g)
    assert res_g.status_code == 200
    assert res_g.json()["isomorphic"] is True

    # Dataset Isomorphism
    req_d = {
        "dataset1": "_:b1 <http://example.org/p> <http://example.org/o> _:g1 .",
        "dataset2": "_:b2 <http://example.org/p> <http://example.org/o> _:g2 ."
    }
    res_d = client.post("/isomorphic/datasets", json=req_d)
    assert res_d.status_code == 200
    assert res_d.json()["isomorphic"] is True


def test_agent_extract_endpoint():
    res = client.post("/agents/extract", json={"text": "Marie Curie was born in Warsaw in 1867."})
    assert res.status_code == 200
    data = res.json()
    assert "extraction" in data
    assert "entities" in data["extraction"]
    assert "relations" in data["extraction"]
    assert "execution_log" in data
    assert "turtle" in data
    assert len(data["extraction"]["entities"]) > 0
    assert len(data["execution_log"]) > 0
