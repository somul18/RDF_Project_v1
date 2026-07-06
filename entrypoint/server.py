import io
from typing import Optional, List, Dict, Union
from fastapi import FastAPI, HTTPException, Query, status, Body
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel, Field
import rdflib

from app.models.rdf import (
    LiteralNode, IRINode, BlankNode, RDFTerm, RDFTriple, RDFQuad, RDFGraph, RDFDataset
)
from app.services.rdf_service import (
    to_rdflib_node, from_rdflib_node,
    to_rdflib_quad, from_rdflib_quad,
    RDFGraphService, RDFDatasetService
)
from rdf11.isomorphism import are_datasets_isomorphic, are_graphs_isomorphic
from rdf11.model import (
    Dataset as CustomDataset,
    Quad as CustomQuad,
    IRI as CustomIRI,
    BlankNode as CustomBNode,
    Literal as CustomLiteral
)

app = FastAPI(
    title="RDF 1.1 HTTP Server",
    description="HTTP API backed by RDFLib to interact with RDF Graphs, Datasets, Quads, and Triples using the app.models API",
    version="3.0.0"
)

# Global in-memory dataset using RDFLib
global_dataset = rdflib.Dataset()


# Convert RDFLib Dataset to custom Dataset representation for isomorphism checks
def rdflib_to_custom_dataset(d: rdflib.Dataset) -> CustomDataset:
    custom_d = CustomDataset()
    for s, p, o, g in d.quads((None, None, None, None)):
        cs = rdflib_to_custom_term(s)
        cp = rdflib_to_custom_term(p)
        co = rdflib_to_custom_term(o)
        
        cg = None
        if g is not None:
            g_str = str(g)
            if g_str != "urn:x-rdflib:default":
                cg = rdflib_to_custom_term(g)
                
        custom_d.add(CustomQuad(cs, cp, co, cg))
    return custom_d


# Helper to convert RDFLib node to custom model term
def rdflib_to_custom_term(node):
    if isinstance(node, rdflib.URIRef):
        return CustomIRI(str(node))
    elif isinstance(node, rdflib.BNode):
        return CustomBNode(str(node))
    elif isinstance(node, rdflib.Literal):
        return CustomLiteral(
            str(node),
            datatype=CustomIRI(str(node.datatype)) if node.datatype else None,
            language=str(node.language) if node.language else None
        )
    return None


# Helper to parse terms from query strings
def parse_query_term(val: Optional[str]) -> Optional[RDFTerm]:
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
        
    if val.startswith('<') and val.endswith('>'):
        return IRINode(val[1:-1])
    if val.startswith('_:'):
        return BlankNode(val[2:])
        
    # Literal parsing
    if val.startswith('"'):
        from rdf11.parser import LineParser
        parser = LineParser(val, 0)
        try:
            parsed_lit = parser.parse_literal()
            return LiteralNode(
                value=parsed_lit.value,
                datatype=parsed_lit.datatype.value if parsed_lit.datatype else None,
                language=parsed_lit.language
            )
        except Exception:
            pass
            
    return LiteralNode(value=val)


# Request Models
class ParseRequest(BaseModel):
    content: str = Field(..., description="Raw text of N-Triples or N-Quads data")
    format: str = Field(..., description="Serialization format: 'ntriples' or 'nquads'")
    graph: Optional[str] = Field(None, description="Optional target graph name (N3 format) to load N-Triples into")


class IsomorphicGraphsRequest(BaseModel):
    graph1: str = Field(..., description="N-Triples string for Graph 1")
    graph2: str = Field(..., description="N-Triples string for Graph 2")


class IsomorphicDatasetsRequest(BaseModel):
    dataset1: str = Field(..., description="N-Quads string for Dataset 1")
    dataset2: str = Field(..., description="N-Quads string for Dataset 2")


@app.post("/clear", status_code=status.HTTP_200_OK)
def clear_dataset():
    """Clear all quads from the global in-memory dataset."""
    global global_dataset
    global_dataset = rdflib.Dataset()
    return {"status": "success", "message": "In-memory dataset cleared"}


@app.post("/parse", response_model=Union[RDFGraph, RDFDataset], status_code=status.HTTP_200_OK)
def parse_rdf(req: ParseRequest):
    """Parse N-Triples or N-Quads and add them to the global dataset, returning the parsed graph/dataset."""
    fmt = req.format.lower()
    
    if fmt == "ntriples":
        try:
            g = rdflib.Graph()
            g.parse(data=req.content, format="nt")
            
            # Determine target context (graph) name
            target_g_uri = None
            if req.graph is not None:
                g_term = parse_query_term(req.graph)
                if g_term is not None:
                    target_g_uri = to_rdflib_node(g_term)
                    
            # Add to global dataset
            ctx_uri = target_g_uri if target_g_uri is not None else rdflib.URIRef("urn:x-rdflib:default")
            ctx = global_dataset.get_context(ctx_uri)
            for t in g:
                ctx.add(t)
                
            return RDFGraphService().from_rdflib_graph(g)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse N-Triples: {e}"
            )
            
    elif fmt == "nquads":
        try:
            d = rdflib.Dataset()
            d.parse(data=req.content, format="nquads")
            
            # Add to global dataset
            for q in d.quads((None, None, None, None)):
                global_dataset.add(q)
                
            return RDFDatasetService().from_rdflib_dataset(d)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse N-Quads: {e}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Must be 'ntriples' or 'nquads'."
        )


@app.get("/quads", response_model=RDFDataset, status_code=status.HTTP_200_OK)
def get_quads(
    s: Optional[str] = Query(None, description="Subject (N3 format)"),
    p: Optional[str] = Query(None, description="Predicate (N3 format)"),
    o: Optional[str] = Query(None, description="Object (N3 format)"),
    g: Optional[str] = Query(None, description="Graph name (N3 format)"),
    match_all_graphs: bool = Query(True, description="If true and 'g' is omitted, search all graphs. Otherwise search only default graph.")
):
    """Query the global dataset with a quad pattern."""
    try:
        s_term = parse_query_term(s)
        p_term = parse_query_term(p)
        o_term = parse_query_term(o)
        g_term = parse_query_term(g)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query parameters: {e}"
        )
        
    s_ref = to_rdflib_node(s_term) if s_term else None
    p_ref = to_rdflib_node(p_term) if p_term else None
    o_ref = to_rdflib_node(o_term) if o_term else None
    
    if g_term is not None:
        g_ref = to_rdflib_node(g_term)
    else:
        g_ref = None if match_all_graphs else rdflib.URIRef("urn:x-rdflib:default")
        
    dataset = RDFDataset()
    raw_quads = list(global_dataset.quads((s_ref, p_ref, o_ref, g_ref)))
    
    # Filter by context manually to handle RDFLib default/union graph behavior
    if g_ref is not None:
        raw_quads = [q for q in raw_quads if q[3] == g_ref]
        
    for sq, pq, oq, gq in raw_quads:
        g_name = "default"
        if gq is not None:
            g_str = str(gq)
            if g_str != "urn:x-rdflib:default":
                g_name = g_str
        
        s_node = from_rdflib_node(sq)
        p_node = from_rdflib_node(pq)
        o_node = from_rdflib_node(oq)
        
        dataset.graph(g_name).add(s_node, p_node, o_node)
        
    return dataset


@app.post("/quads", status_code=status.HTTP_201_CREATED)
def add_quad(quad: RDFQuad):
    """Add a quad (using the Pydantic RDFQuad model) to the global dataset."""
    try:
        s, p, o, g = to_rdflib_quad(quad)
        g_ref = g if g is not None else rdflib.URIRef("urn:x-rdflib:default")
        global_dataset.add((s, p, o, g_ref))
        return {"status": "success", "quad": quad}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add quad: {e}"
        )


@app.delete("/quads", status_code=status.HTTP_200_OK)
def delete_quads(
    s: Optional[str] = Query(None, description="Subject (N3 format)"),
    p: Optional[str] = Query(None, description="Predicate (N3 format)"),
    o: Optional[str] = Query(None, description="Object (N3 format)"),
    g: Optional[str] = Query(None, description="Graph name (N3 format)"),
    match_all_graphs: bool = Query(True, description="If true and 'g' is omitted, delete from all graphs. Otherwise delete only from default graph.")
):
    """Delete quads matching the pattern from the global dataset."""
    try:
        s_term = parse_query_term(s)
        p_term = parse_query_term(p)
        o_term = parse_query_term(o)
        g_term = parse_query_term(g)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid delete parameters: {e}"
        )
        
    s_ref = to_rdflib_node(s_term) if s_term else None
    p_ref = to_rdflib_node(p_term) if p_term else None
    o_ref = to_rdflib_node(o_term) if o_term else None
    
    if g_term is not None:
        g_ref = to_rdflib_node(g_term)
    else:
        g_ref = None if match_all_graphs else rdflib.URIRef("urn:x-rdflib:default")
        
    # Find matching quads first
    matching = list(global_dataset.quads((s_ref, p_ref, o_ref, g_ref)))
    for q in matching:
        global_dataset.remove(q)
        
    return {"status": "success", "quads_removed": len(matching)}


@app.get("/serialize", response_class=PlainTextResponse)
def serialize_rdf(
    format: str = Query("nquads", description="Serialization format: 'ntriples' or 'nquads'"),
    graph: Optional[str] = Query(None, description="Graph name (N3 format) to serialize as N-Triples")
):
    """Serialize the global dataset or a target named graph to text."""
    fmt = format.lower()
    try:
        if fmt == "ntriples":
            g_term = parse_query_term(graph) if graph is not None else None
            g_ref = to_rdflib_node(g_term) if g_term else rdflib.URIRef("urn:x-rdflib:default")
            ctx = global_dataset.get_context(g_ref)
            res_bytes = ctx.serialize(format="nt")
            return res_bytes.decode("utf-8") if isinstance(res_bytes, bytes) else res_bytes
        elif fmt == "nquads":
            if graph is not None:
                raise ValueError("Graph option is not supported for N-Quads format")
            res_bytes = global_dataset.serialize(format="nquads")
            return res_bytes.decode("utf-8") if isinstance(res_bytes, bytes) else res_bytes
        else:
            raise ValueError("Format must be 'ntriples' or 'nquads'")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Serialization failed: {e}"
        )


@app.post("/isomorphic/graphs", status_code=status.HTTP_200_OK)
def check_graphs_isomorphic(req: IsomorphicGraphsRequest):
    """Parse and check if two N-Triples graphs are isomorphic."""
    try:
        g1 = rdflib.Graph()
        g1.parse(data=req.graph1, format="nt")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Graph 1: {e}"
        )
        
    try:
        g2 = rdflib.Graph()
        g2.parse(data=req.graph2, format="nt")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Graph 2: {e}"
        )
        
    from rdflib.compare import isomorphic
    isomorphic_res = isomorphic(g1, g2)
    return {"isomorphic": isomorphic_res}


@app.post("/isomorphic/datasets", status_code=status.HTTP_200_OK)
def check_datasets_isomorphic(req: IsomorphicDatasetsRequest):
    """Parse and check if two N-Quads datasets are isomorphic using the custom isomorphism engine."""
    try:
        d1 = rdflib.Dataset()
        d1.parse(data=req.dataset1, format="nquads")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Dataset 1: {e}"
        )
        
    try:
        d2 = rdflib.Dataset()
        d2.parse(data=req.dataset2, format="nquads")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Dataset 2: {e}"
        )
        
    # Convert to custom dataset representation for our abstract syntax isomorphism engine
    custom_d1 = rdflib_to_custom_dataset(d1)
    custom_d2 = rdflib_to_custom_dataset(d2)
    
    isomorphic_res = are_datasets_isomorphic(custom_d1, custom_d2)
    return {"isomorphic": isomorphic_res}


# Agent Workflow request model
class AgentWorkflowRequest(BaseModel):
    text: str


@app.post("/agents/extract")
def run_agent_workflow(req: AgentWorkflowRequest):
    """Run the multi-agent pipeline to extract, map, and validate RDF graphs from text."""
    try:
        from agents.graph_workflow import RDFGraphWorkflow
        from agents.extractor_agent import EntityExtractorAgent, RelationExtractorAgent
        from agents.rdf_builder_agent import RDFBuilderAgent
        from agents.validator_agent import ValidatorAgent
        
        workflow = RDFGraphWorkflow(
            EntityExtractorAgent(),
            RelationExtractorAgent(),
            RDFBuilderAgent(),
            ValidatorAgent()
        )
        
        res = workflow.run(req.text)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow execution failed: {e}"
        )


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Serve the interactive developer demo UI."""
    import os
    from fastapi.responses import HTMLResponse
    
    ui_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UIs", "index.html"))
    try:
        with open(ui_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read index.html: {e}"
        )
