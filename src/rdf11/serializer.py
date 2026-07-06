from .model import Graph, Dataset


def serialize_n_triples(graph: Graph) -> str:
    """Serialize an RDF Graph to N-Triples format.

    The output is sorted by line content for determinism.
    """
    if not isinstance(graph, Graph):
        raise TypeError("Expected an instance of Graph")
        
    lines = []
    for t in graph:
        lines.append(f"{t.subject.n3()} {t.predicate.n3()} {t.object.n3()} .")
        
    lines.sort()
    return "\n".join(lines) + "\n" if lines else ""


def serialize_n_quads(dataset: Dataset) -> str:
    """Serialize an RDF Dataset to N-Quads format.

    The output is sorted by line content for determinism.
    """
    if not isinstance(dataset, Dataset):
        raise TypeError("Expected an instance of Dataset")
        
    lines = []
    for q in dataset:
        if q.graph_name is None:
            lines.append(f"{q.subject.n3()} {q.predicate.n3()} {q.object.n3()} .")
        else:
            lines.append(f"{q.subject.n3()} {q.predicate.n3()} {q.object.n3()} {q.graph_name.n3()} .")
            
    lines.sort()
    return "\n".join(lines) + "\n" if lines else ""
