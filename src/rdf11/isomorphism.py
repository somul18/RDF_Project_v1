import hashlib
from typing import Dict, Set, List, Optional, Union, Tuple as PyTuple
from .model import Graph, Dataset, Triple, Quad, BlankNode, IRI, Literal, RDFTerm


def get_graph_bnodes(graph: Graph) -> Set[BlankNode]:
    """Collect all blank nodes in a graph."""
    bnodes = set()
    for t in graph:
        if isinstance(t.subject, BlankNode):
            bnodes.add(t.subject)
        if isinstance(t.object, BlankNode):
            bnodes.add(t.object)
    return bnodes


def color_graph_bnodes(graph: Graph, bnodes: Set[BlankNode]) -> Dict[BlankNode, str]:
    """Color blank nodes in a graph using iterative neighbor signature hashing."""
    colors = {b: "BNODE" for b in bnodes}

    def get_color(node: RDFTerm) -> str:
        if isinstance(node, BlankNode):
            return colors.get(node, "BNODE")
        return node.n3()

    num_bnodes = len(bnodes)
    for _ in range(num_bnodes + 1):
        new_colors = {}
        for b in bnodes:
            features = []
            for t in graph.triples(s=b):
                features.append(("s", t.predicate.n3(), get_color(t.object)))
            for t in graph.triples(o=b):
                features.append(("o", get_color(t.subject), t.predicate.n3()))
            
            features.sort()
            hasher = hashlib.sha256()
            for f in features:
                hasher.update(str(f).encode("utf-8"))
            new_colors[b] = hasher.hexdigest()
            
        if new_colors == colors:
            break
        colors = new_colors
        
    return colors


def are_graphs_isomorphic(g1: Graph, g2: Graph) -> bool:
    """Determine if two RDF Graphs are isomorphic."""
    if not isinstance(g1, Graph) or not isinstance(g2, Graph):
        raise TypeError("Arguments must be Graph instances")
        
    # Quick size check
    if len(g1) != len(g2):
        return False
        
    bnodes_g1 = get_graph_bnodes(g1)
    bnodes_g2 = get_graph_bnodes(g2)
    
    if len(bnodes_g1) != len(bnodes_g2):
        return False
        
    if not bnodes_g1:
        # No blank nodes, graphs must be identical sets of triples
        return g1._triples == g2._triples

    # Color refinement
    colors_g1 = color_graph_bnodes(g1, bnodes_g1)
    colors_g2 = color_graph_bnodes(g2, bnodes_g2)
    
    # Group by colors
    groups_g1: Dict[str, List[BlankNode]] = {}
    for b, c in colors_g1.items():
        groups_g1.setdefault(c, []).append(b)
        
    groups_g2: Dict[str, List[BlankNode]] = {}
    for b, c in colors_g2.items():
        groups_g2.setdefault(c, []).append(b)
        
    if groups_g1.keys() != groups_g2.keys():
        return False
        
    for c in groups_g1:
        if len(groups_g1[c]) != len(groups_g2[c]):
            return False
            
    # Sort color groups by size to match most constrained first
    sorted_colors = sorted(groups_g1.keys(), key=lambda col: len(groups_g1[col]))
    bnodes_list = []
    for c in sorted_colors:
        bnodes_list.extend(groups_g1[c])
        
    # Pre-map non-blank nodes to themselves
    current_map: Dict[BlankNode, BlankNode] = {}
    mapped_g2: Set[BlankNode] = set()

    def is_locally_consistent(b: BlankNode, bp: BlankNode) -> bool:
        # Check triples where b is subject
        for t in g1.triples(s=b):
            p = t.predicate
            o = t.object
            if isinstance(o, BlankNode):
                if o in current_map:
                    if Triple(bp, p, current_map[o]) not in g2:
                        return False
            else:
                if Triple(bp, p, o) not in g2:
                    return False
                    
        # Check triples where b is object
        for t in g1.triples(o=b):
            p = t.predicate
            s = t.subject
            if isinstance(s, BlankNode):
                if s in current_map:
                    if Triple(current_map[s], p, bp) not in g2:
                        return False
            else:
                if Triple(s, p, bp) not in g2:
                    return False
        return True

    def backtrack(idx: int) -> bool:
        if idx == len(bnodes_list):
            # Double check all triples under the bijection
            mapped_triples = set()
            for t in g1:
                s = current_map.get(t.subject, t.subject) if isinstance(t.subject, BlankNode) else t.subject
                o = current_map.get(t.object, t.object) if isinstance(t.object, BlankNode) else t.object
                mapped_triples.add(Triple(s, t.predicate, o))
            return mapped_triples == g2._triples
            
        b = bnodes_list[idx]
        c = colors_g1[b]
        for bp in groups_g2[c]:
            if bp not in mapped_g2:
                if is_locally_consistent(b, bp):
                    current_map[b] = bp
                    mapped_g2.add(bp)
                    if backtrack(idx + 1):
                        return True
                    mapped_g2.remove(bp)
                    del current_map[b]
        return False

    return backtrack(0)


def get_dataset_bnodes(dataset: Dataset) -> Set[BlankNode]:
    """Collect all blank nodes in a dataset."""
    bnodes = set()
    for q in dataset:
        if isinstance(q.subject, BlankNode):
            bnodes.add(q.subject)
        if isinstance(q.object, BlankNode):
            bnodes.add(q.object)
        if isinstance(q.graph_name, BlankNode):
            bnodes.add(q.graph_name)
    return bnodes


def color_dataset_bnodes(dataset: Dataset, bnodes: Set[BlankNode]) -> Dict[BlankNode, str]:
    """Color blank nodes in a dataset using iterative neighbor signature hashing."""
    colors = {b: "BNODE" for b in bnodes}

    def get_color(node: Optional[RDFTerm]) -> str:
        if node is None:
            return "DEFAULT"
        if isinstance(node, BlankNode):
            return colors.get(node, "BNODE")
        return node.n3()

    num_bnodes = len(bnodes)
    for _ in range(num_bnodes + 1):
        new_colors = {}
        for b in bnodes:
            features = []
            # Query dataset using our quads method
            # If b is subject
            for q in dataset.quads(s=b):
                features.append(("s", q.predicate.n3(), get_color(q.object), get_color(q.graph_name)))
            # If b is object
            for q in dataset.quads(o=b):
                features.append(("o", get_color(q.subject), q.predicate.n3(), get_color(q.graph_name)))
            # If b is graph name
            for q in dataset.quads(g=b):
                features.append(("g", get_color(q.subject), q.predicate.n3(), get_color(q.object)))
                
            features.sort()
            hasher = hashlib.sha256()
            for f in features:
                hasher.update(str(f).encode("utf-8"))
            new_colors[b] = hasher.hexdigest()
            
        if new_colors == colors:
            break
        colors = new_colors
        
    return colors


def are_datasets_isomorphic(d1: Dataset, d2: Dataset) -> bool:
    """Determine if two RDF Datasets are isomorphic."""
    if not isinstance(d1, Dataset) or not isinstance(d2, Dataset):
        raise TypeError("Arguments must be Dataset instances")
        
    if len(d1) != len(d2):
        return False
        
    bnodes_d1 = get_dataset_bnodes(d1)
    bnodes_d2 = get_dataset_bnodes(d2)
    
    if len(bnodes_d1) != len(bnodes_d2):
        return False
        
    # Check default graph and named graphs lists match in size
    # By listing non-empty graph names
    gnames1 = set(d1.graph_names())
    gnames2 = set(d2.graph_names())
    
    # Non-blank graph names must match exactly
    non_blank_gnames1 = {gn for gn in gnames1 if not isinstance(gn, BlankNode)}
    non_blank_gnames2 = {gn for gn in gnames2 if not isinstance(gn, BlankNode)}
    if non_blank_gnames1 != non_blank_gnames2:
        return False
        
    if not bnodes_d1:
        # No blank nodes, datasets must contain exactly same quads
        return set(d1) == set(d2)

    # Color refinement
    colors_d1 = color_dataset_bnodes(d1, bnodes_d1)
    colors_d2 = color_dataset_bnodes(d2, bnodes_d2)
    
    groups_d1: Dict[str, List[BlankNode]] = {}
    for b, c in colors_d1.items():
        groups_d1.setdefault(c, []).append(b)
        
    groups_d2: Dict[str, List[BlankNode]] = {}
    for b, c in colors_d2.items():
        groups_d2.setdefault(c, []).append(b)
        
    if groups_d1.keys() != groups_d2.keys():
        return False
        
    for c in groups_d1:
        if len(groups_d1[c]) != len(groups_d2[c]):
            return False
            
    sorted_colors = sorted(groups_d1.keys(), key=lambda col: len(groups_d1[col]))
    bnodes_list = []
    for c in sorted_colors:
        bnodes_list.extend(groups_d1[c])
        
    current_map: Dict[BlankNode, BlankNode] = {}
    mapped_d2: Set[BlankNode] = set()

    def is_locally_consistent(b: BlankNode, bp: BlankNode) -> bool:
        # Check all quads where b is subject, object, or graph name
        # Subject check
        for q in d1.quads(s=b):
            p = q.predicate
            o = q.object
            g = q.graph_name
            # map object if blank node
            om = current_map.get(o, o) if isinstance(o, BlankNode) else o
            gm = current_map.get(g, g) if isinstance(g, BlankNode) else g
            # if either is blank node and not yet mapped, we skip local checking for that component
            if (isinstance(o, BlankNode) and o not in current_map) or (isinstance(g, BlankNode) and g not in current_map):
                continue
            if Quad(bp, p, om, gm) not in d2:
                return False
                
        # Object check
        for q in d1.quads(o=b):
            p = q.predicate
            s = q.subject
            g = q.graph_name
            sm = current_map.get(s, s) if isinstance(s, BlankNode) else s
            gm = current_map.get(g, g) if isinstance(g, BlankNode) else g
            if (isinstance(s, BlankNode) and s not in current_map) or (isinstance(g, BlankNode) and g not in current_map):
                continue
            if Quad(sm, p, bp, gm) not in d2:
                return False
                
        # Graph name check
        for q in d1.quads(g=b):
            p = q.predicate
            s = q.subject
            o = q.object
            sm = current_map.get(s, s) if isinstance(s, BlankNode) else s
            om = current_map.get(o, o) if isinstance(o, BlankNode) else o
            if (isinstance(s, BlankNode) and s not in current_map) or (isinstance(o, BlankNode) and o not in current_map):
                continue
            if Quad(sm, p, om, bp) not in d2:
                return False
                
        return True

    def backtrack(idx: int) -> bool:
        if idx == len(bnodes_list):
            mapped_quads = set()
            for q in d1:
                s = current_map.get(q.subject, q.subject) if isinstance(q.subject, BlankNode) else q.subject
                o = current_map.get(q.object, q.object) if isinstance(q.object, BlankNode) else q.object
                g = current_map.get(q.graph_name, q.graph_name) if isinstance(q.graph_name, BlankNode) else q.graph_name
                mapped_quads.add(Quad(s, q.predicate, o, g))
            return mapped_quads == set(d2)
            
        b = bnodes_list[idx]
        c = colors_d1[b]
        for bp in groups_d2[c]:
            if bp not in mapped_d2:
                if is_locally_consistent(b, bp):
                    current_map[b] = bp
                    mapped_d2.add(bp)
                    if backtrack(idx + 1):
                        return True
                    mapped_d2.remove(bp)
                    del current_map[b]
        return False

    return backtrack(0)
