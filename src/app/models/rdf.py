from typing import List, Optional, Union, Any, Dict, Annotated, Literal
from pydantic import BaseModel, Field, computed_field


class RDFNamespace(BaseModel):
    """Represent an RDF Namespace with prefix and URI."""
    prefix: str
    uri: str

    def __init__(self, prefix: str, uri: str, **kwargs):
        super().__init__(prefix=prefix, uri=uri, **kwargs)

    def __getattr__(self, name: str) -> "IRINode":
        return IRINode(self.uri + name)

    def __getitem__(self, name: str) -> "IRINode":
        return IRINode(self.uri + name)


class RDFTerm(BaseModel):
    """Abstract base class for all RDF Terms."""
    
    def __hash__(self):
        return hash((self.__class__.__name__, str(self.model_dump())))

    def __eq__(self, other):
        if not isinstance(other, RDFTerm):
            return False
        return self.model_dump() == other.model_dump()


class IRINode(RDFTerm):
    """Represent an IRI Node."""
    type: Literal["uri"] = "uri"
    value: str

    def __init__(self, value: str, **kwargs):
        super().__init__(value=value, **kwargs)


class BlankNode(RDFTerm):
    """Represent a Blank Node."""
    type: Literal["bnode"] = "bnode"
    value: str

    def __init__(self, value: str, **kwargs):
        super().__init__(value=value, **kwargs)


class LiteralNode(RDFTerm):
    """Represent a Literal Node with support for native Python types."""
    type: Literal["literal"] = "literal"
    value: Any
    datatype: Optional[str] = None
    language: Optional[str] = None

    def __init__(
        self,
        value: Any,
        datatype: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs
    ):
        super().__init__(value=value, datatype=datatype, language=language, **kwargs)


# Discriminator-based union for robust Pydantic parsing of polymorphic terms
RDFTermUnion = Annotated[Union[IRINode, BlankNode, LiteralNode], Field(discriminator="type")]
SubjectUnion = Annotated[Union[IRINode, BlankNode], Field(discriminator="type")]


class RDFTriple(BaseModel):
    """Represent an RDF Triple."""
    subject: SubjectUnion
    predicate: IRINode
    object: RDFTermUnion

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


class RDFSubjectBuilder:
    """Fluent builder for adding triples relative to a subject."""
    
    def __init__(self, graph: 'RDFGraph', subject: Union[str, RDFTerm]):
        self.graph = graph
        self.subject = self.graph._create_node(subject)

    def __getattr__(self, name: str):
        # Support fluent builder calls: .born_in("Warsaw")
        def _add_triple(value: Any):
            if name == "type":
                pred = "rdf:type"
            else:
                pred = f"ex:{name}"

            # Convert value to RDFTerm
            if isinstance(value, RDFTerm):
                obj = value
            elif isinstance(value, (int, float, bool)):
                obj = LiteralNode(value)
            elif isinstance(value, str):
                if ":" in value or value.startswith("http"):
                    obj = self.graph._create_node(value)
                elif " " in value:
                    obj = LiteralNode(value)
                else:
                    obj = self.graph._create_node(f"ex:{value}")
            else:
                obj = LiteralNode(value)

            self.graph.add(self.subject, pred, obj)
            return self
        return _add_triple


class RDFGraph(BaseModel):
    """Represent an RDF Graph with Namespace, builder, and query support."""
    graph_id: str
    triples: List[RDFTriple] = Field(default_factory=list)
    namespaces: Dict[str, str] = Field(default_factory=dict)

    def __getattr__(self, name: str):
        def _start_builder(subject_val: str):
            if ":" not in subject_val and not subject_val.startswith("http"):
                subj_str = f"ex:{subject_val}"
            else:
                subj_str = subject_val
            
            class_name = name.capitalize()
            self.add_type(subj_str, f"ex:{class_name}")
            
            return RDFSubjectBuilder(self, subj_str)
        return _start_builder

    def bind(self, prefix_or_ns: Union[str, RDFNamespace], namespace: Optional[str] = None):
        """Bind a namespace prefix or RDFNamespace instance to a URI."""
        if isinstance(prefix_or_ns, RDFNamespace):
            self.namespaces[prefix_or_ns.prefix] = prefix_or_ns.uri
        elif isinstance(prefix_or_ns, str):
            if namespace is None:
                raise ValueError("Namespace URI must be provided when prefix is a string")
            self.namespaces[prefix_or_ns] = namespace
        else:
            raise TypeError("Expected RDFNamespace or prefix string")

    def namespace(self, prefix: str) -> Optional[RDFNamespace]:
        """Get the RDFNamespace object for the registered prefix."""
        if prefix in self.namespaces:
            return RDFNamespace(prefix, self.namespaces[prefix])
        return None

    def expand_prefix(self, val: str) -> str:
        """Expand a prefix to its full namespace URI if it exists."""
        if ":" in val:
            prefix, local = val.split(":", 1)
            if prefix in self.namespaces:
                return self.namespaces[prefix] + local
        return val

    def _resolve_node(self, node: RDFTerm) -> RDFTerm:
        if isinstance(node, IRINode):
            return IRINode(self.expand_prefix(node.value))
        return node

    def _create_node(self, val: Union[str, RDFTerm]) -> RDFTerm:
        if isinstance(val, RDFTerm):
            return val
        if not isinstance(val, str):
            raise TypeError("Expected string or RDFTerm")
        if val.startswith("_:"):
            return BlankNode(val)
        return IRINode(val)

    def add(
        self,
        subject: Union[str, IRINode, BlankNode],
        predicate: Union[str, IRINode],
        object: Union[str, IRINode, BlankNode, LiteralNode]
    ):
        """Add a triple directly to the graph, expanding prefixes if bound."""
        resolved_s = self._resolve_node(self._create_node(subject))
        resolved_p = self._resolve_node(self._create_node(predicate))
        resolved_o = self._resolve_node(self._create_node(object))

        if not isinstance(resolved_s, (IRINode, BlankNode)):
            raise TypeError("Subject must be an IRINode or BlankNode")
        if not isinstance(resolved_p, IRINode):
            raise TypeError("Predicate must be an IRINode")
        if not isinstance(resolved_o, (IRINode, BlankNode, LiteralNode)):
            raise TypeError("Object must be an IRINode, BlankNode, or LiteralNode")
            
        self.triples.append(RDFTriple(subject=resolved_s, predicate=resolved_p, object=resolved_o))

    def add_type(self, subject: Union[str, IRINode, BlankNode], type_node: Union[str, IRINode]):
        """Helper to add an rdf:type triple."""
        s = self._create_node(subject)
        t = self._create_node(type_node)
        self.add(s, IRINode("rdf:type"), t)

    def add_literal(
        self,
        subject: Union[str, IRINode, BlankNode],
        predicate: Union[str, IRINode],
        value: Any,
        datatype: Optional[str] = None,
        language: Optional[str] = None
    ):
        """Helper to add a literal triple."""
        s = self._create_node(subject)
        p = self._create_node(predicate)
        o = LiteralNode(value, datatype=datatype, language=language)
        self.add(s, p, o)

    def remove(
        self,
        subject: Optional[Union[str, RDFTerm]] = None,
        predicate: Optional[Union[str, RDFTerm]] = None,
        object: Optional[Union[str, RDFTerm]] = None
    ):
        """Remove all triples matching the specified pattern from the graph."""
        s_pattern = self._resolve_node(self._create_node(subject)) if subject is not None else None
        p_pattern = self._resolve_node(self._create_node(predicate)) if predicate is not None else None
        o_pattern = self._resolve_node(self._create_node(object)) if object is not None else None

        new_triples = []
        for t in self.triples:
            match_s = (s_pattern is None) or (t.subject == s_pattern)
            match_p = (p_pattern is None) or (t.predicate == p_pattern)
            match_o = (o_pattern is None) or (t.object == o_pattern)
            if not (match_s and match_p and match_o):
                new_triples.append(t)
        self.triples = new_triples

    def find(
        self,
        subject: Optional[Union[str, RDFTerm]] = None,
        predicate: Optional[Union[str, RDFTerm]] = None,
        object: Optional[Union[str, RDFTerm]] = None
    ) -> List[RDFTriple]:
        """Find and return triples matching the specified pattern."""
        s_pattern = self._resolve_node(self._create_node(subject)) if subject is not None else None
        p_pattern = self._resolve_node(self._create_node(predicate)) if predicate is not None else None
        o_pattern = self._resolve_node(self._create_node(object)) if object is not None else None

        results = []
        for t in self.triples:
            match_s = (s_pattern is None) or (t.subject == s_pattern)
            match_p = (p_pattern is None) or (t.predicate == p_pattern)
            match_o = (o_pattern is None) or (t.object == o_pattern)
            if match_s and match_p and match_o:
                results.append(t)
        return results

    def subjects(
        self,
        predicate: Optional[Union[str, RDFTerm]] = None,
        object: Optional[Union[str, RDFTerm]] = None
    ) -> List[Union[IRINode, BlankNode]]:
        """Return unique subjects matching the pattern."""
        matching = self.find(None, predicate, object)
        seen = set()
        results = []
        for t in matching:
            if t.subject not in seen:
                seen.add(t.subject)
                results.append(t.subject)
        return results

    def predicates(
        self,
        subject: Optional[Union[str, RDFTerm]] = None,
        object: Optional[Union[str, RDFTerm]] = None
    ) -> List[IRINode]:
        """Return unique predicates matching the pattern."""
        matching = self.find(subject, None, object)
        seen = set()
        results = []
        for t in matching:
            if t.predicate not in seen:
                seen.add(t.predicate)
                results.append(t.predicate)
        return results

    def objects(
        self,
        subject: Optional[Union[str, RDFTerm]] = None,
        predicate: Optional[Union[str, RDFTerm]] = None
    ) -> List[Union[IRINode, BlankNode, LiteralNode]]:
        """Return unique objects matching the pattern."""
        matching = self.find(subject, predicate, None)
        seen = set()
        results = []
        for t in matching:
            if t.object not in seen:
                seen.add(t.object)
                results.append(t.object)
        return results

    def contains(
        self,
        subject: Union[str, RDFTerm, RDFTriple],
        predicate: Optional[Union[str, RDFTerm]] = None,
        object: Optional[Union[str, RDFTerm]] = None
    ) -> bool:
        """Check if the graph contains at least one triple matching the pattern/triple."""
        if isinstance(subject, RDFTriple):
            return len(self.find(subject.subject, subject.predicate, subject.object)) > 0
        return len(self.find(subject, predicate, object)) > 0

    def serialize(self, format: str) -> str:
        """Serialize this graph using the RDFGraphService."""
        from app.services.rdf_service import RDFGraphService
        return RDFGraphService().serialize(self, format)


class RDFQuad(BaseModel):
    """Represent an RDF Quad."""
    subject: SubjectUnion
    predicate: IRINode
    object: RDFTermUnion
    graph: Optional[SubjectUnion] = None

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object, self.graph))


class RDFDataset(BaseModel):
    """Represent an RDF Dataset with Graph view management."""
    graphs: Dict[str, RDFGraph] = Field(default_factory=dict)
    namespaces: Dict[str, str] = Field(default_factory=dict)

    def bind(self, prefix_or_ns: Union[str, RDFNamespace], namespace: Optional[str] = None):
        """Bind a namespace prefix or RDFNamespace instance to a URI."""
        if isinstance(prefix_or_ns, RDFNamespace):
            prefix = prefix_or_ns.prefix
            uri = prefix_or_ns.uri
        elif isinstance(prefix_or_ns, str):
            if namespace is None:
                raise ValueError("Namespace URI must be provided when prefix is a string")
            prefix = prefix_or_ns
            uri = namespace
        else:
            raise TypeError("Expected RDFNamespace or prefix string")

        self.namespaces[prefix] = uri
        # Propagate to existing graphs
        for g in self.graphs.values():
            g.bind(prefix, uri)

    def namespace(self, prefix: str) -> Optional[RDFNamespace]:
        """Get the RDFNamespace object for the registered prefix."""
        if prefix in self.namespaces:
            return RDFNamespace(prefix, self.namespaces[prefix])
        return None

    def default_graph(self) -> RDFGraph:
        """Get or create the default graph."""
        return self.graph("default")

    def graph(self, graph_name: str) -> RDFGraph:
        """Get or create a named graph."""
        if graph_name not in self.graphs:
            # Create dynamic graph and copy namespaces
            g = RDFGraph(graph_id=graph_name, namespaces=self.namespaces.copy())
            self.graphs[graph_name] = g
        return self.graphs[graph_name]

    def expand_prefix(self, val: str) -> str:
        """Expand a prefix to its full namespace URI if it exists."""
        if ":" in val:
            prefix, local = val.split(":", 1)
            if prefix in self.namespaces:
                return self.namespaces[prefix] + local
        return val

    @computed_field
    @property
    def quads(self) -> List[RDFQuad]:
        """Dynamically assemble the list of all quads from all graphs."""
        quad_list = []
        for name, g in self.graphs.items():
            if name == "default":
                g_node = None
            else:
                # Resolve prefix for named graph if it has one
                expanded_name = self.expand_prefix(name)
                g_node = IRINode(expanded_name)

            for t in g.triples:
                quad_list.append(
                    RDFQuad(
                        subject=t.subject,
                        predicate=t.predicate,
                        object=t.object,
                        graph=g_node
                    )
                )
        return quad_list

    def serialize(self, format: str) -> str:
        """Serialize this dataset using the RDFDatasetService."""
        from app.services.rdf_service import RDFDatasetService
        return RDFDatasetService().serialize(self, format)
