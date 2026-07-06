from typing import Union
from .model import RDFTerm, IRI, BlankNode, Literal, Triple, Quad


def term_to_json(term: RDFTerm) -> dict:
    """Convert an RDFTerm (IRI, BlankNode, or Literal) to a standard JSON representation."""
    if not isinstance(term, RDFTerm):
        raise TypeError("Expected an instance of RDFTerm")

    if isinstance(term, IRI):
        return {"type": "uri", "value": term.value}
    elif isinstance(term, BlankNode):
        return {"type": "bnode", "value": term.value}
    elif isinstance(term, Literal):
        result = {
            "type": "literal",
            "value": term.value
        }
        if term.language is not None:
            result["xml:lang"] = term.language
        if term.datatype is not None:
            result["datatype"] = term.datatype.value
        return result
    else:
        raise ValueError(f"Unknown RDFTerm type: {type(term)}")


def json_to_term(data: dict) -> RDFTerm:
    """Convert a JSON dictionary back to an RDFTerm."""
    if not isinstance(data, dict):
        raise TypeError("JSON data for term must be a dictionary")
    
    term_type = data.get("type")
    value = data.get("value")
    
    if value is None:
        raise ValueError("Term representation must contain a 'value' field")
    if not isinstance(value, str):
        raise TypeError("Term value must be a string")
        
    if term_type == "uri":
        return IRI(value)
    elif term_type == "bnode":
        return BlankNode(value)
    elif term_type == "literal":
        lang = data.get("xml:lang") or data.get("language")
        datatype_str = data.get("datatype")
        
        datatype = IRI(datatype_str) if datatype_str is not None else None
        
        return Literal(value, datatype=datatype, language=lang)
    else:
        raise ValueError(f"Invalid term type: {term_type}")


def triple_to_json(triple: Triple) -> dict:
    """Convert a Triple to a JSON dictionary."""
    if not isinstance(triple, Triple):
        raise TypeError("Expected an instance of Triple")
    return {
        "subject": term_to_json(triple.subject),
        "predicate": term_to_json(triple.predicate),
        "object": term_to_json(triple.object)
    }


def json_to_triple(data: dict) -> Triple:
    """Convert a JSON dictionary to a Triple."""
    if not isinstance(data, dict):
        raise TypeError("JSON data for triple must be a dictionary")
    s = json_to_term(data["subject"])
    p = json_to_term(data["predicate"])
    o = json_to_term(data["object"])
    return Triple(s, p, o)


def quad_to_json(quad: Quad) -> dict:
    """Convert a Quad to a JSON dictionary."""
    if not isinstance(quad, Quad):
        raise TypeError("Expected an instance of Quad")
    return {
        "subject": term_to_json(quad.subject),
        "predicate": term_to_json(quad.predicate),
        "object": term_to_json(quad.object),
        "graph": term_to_json(quad.graph_name) if quad.graph_name is not None else None
    }


def json_to_quad(data: dict) -> Quad:
    """Convert a JSON dictionary to a Quad."""
    if not isinstance(data, dict):
        raise TypeError("JSON data for quad must be a dictionary")
    s = json_to_term(data["subject"])
    p = json_to_term(data["predicate"])
    o = json_to_term(data["object"])
    
    graph_data = data.get("graph")
    g = json_to_term(graph_data) if graph_data is not None else None
    
    return Quad(s, p, o, g)
