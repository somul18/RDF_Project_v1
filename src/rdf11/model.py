import re
import uuid
from typing import Union, Generator, Optional, Set, Dict, Iterator, Tuple as PyTuple, Iterable
from urllib.parse import urlsplit

RDF_LANG_STRING_STR = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"
XSD_STRING_STR = "http://www.w3.org/2001/XMLSchema#string"

# BCP 47 (RFC 5646) well-formed language tag regex
# This matches the ABNF grammar for well-formed language tags.
BCP47_PATTERN = re.compile(
    r'^(?:'
    # Regular language tags
    r'(?:[a-zA-Z]{2,3}(?:-[a-zA-Z]{3}){0,3}|[a-zA-Z]{4}|[a-zA-Z]{5,8})'  # language
    r'(?:-[a-zA-Z]{4})?'                                                 # script
    r'(?:-[a-zA-Z]{2}|-[0-9]{3})?'                                       # region
    r'(?:-(?:[a-zA-Z0-9]{5,8}|[0-9][a-zA-Z0-9]{3}))*'                     # variant
    r'(?:-[0-9A-WY-Za-wy-z](?:-[a-zA-Z0-9]{2,8})+)*'                     # extension
    r'(?:-x(?:-[a-zA-Z0-9]{1,8})+)?'                                     # privateuse
    # Private use only
    r'|x(?:-[a-zA-Z0-9]{1,8})+'
    # Grandfathered or registered tags (simplified check matching structural rules)
    r'|[a-zA-Z]{1,3}(?:-[a-zA-Z0-9]{2,8}){1,2}'
    r')$'
)

# URI/IRI scheme regex (RFC 3986 / RFC 3987)
SCHEME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9.+-]*$')


class RDFTerm:
    """Base class for all RDF Terms (IRIs, Blank Nodes, and Literals)."""
    __slots__ = ()

    def __repr__(self) -> str:
        return self.n3()

    def n3(self) -> str:
        """Return the N-Triples/N3 representation of the term."""
        raise NotImplementedError


class IRI(RDFTerm):
    """An Internationalized Resource Identifier (IRI)."""
    __slots__ = ("_value",)

    def __init__(self, value: str):
        if not isinstance(value, str):
            raise TypeError("IRI value must be a string")
        
        # Check that it's an absolute IRI
        # Parse scheme using urlsplit
        parts = urlsplit(value)
        if not parts.scheme:
            raise ValueError(f"IRI must be absolute (scheme is missing): {value}")
        if not SCHEME_PATTERN.match(parts.scheme):
            raise ValueError(f"Invalid scheme in IRI: {parts.scheme}")
            
        self._value: str = value

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IRI):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash((IRI, self._value))

    def n3(self) -> str:
        # Standard N-Triples serialization escapes for IRIs:
        # Characters like \u0000-\u0020, <, >, ", {, }, |, ^, `, \ should be escaped.
        # But we will use the standard IRI wrapper for now.
        return f"<{self._value}>"


class BlankNode(RDFTerm):
    """An RDF Blank Node."""
    __slots__ = ("_value",)

    def __init__(self, value: Optional[str] = None):
        if value is None:
            # Auto-generate a unique ID
            self._value: str = f"b{uuid.uuid4().hex}"
        else:
            if not isinstance(value, str):
                raise TypeError("BlankNode value must be a string")
            # If it starts with '_:', strip it for canonical storage
            if value.startswith("_:"):
                value = value[2:]
            if not value:
                raise ValueError("BlankNode identifier cannot be empty")
            self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BlankNode):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash((BlankNode, self._value))

    def n3(self) -> str:
        return f"_:{self._value}"


class Literal(RDFTerm):
    """An RDF Literal representing strings, numbers, dates, etc."""
    __slots__ = ("_value", "_datatype", "_language")

    def __init__(
        self,
        value: str,
        datatype: Optional[IRI] = None,
        language: Optional[str] = None
    ):
        if not isinstance(value, str):
            raise TypeError("Literal lexical form (value) must be a string")

        self._value: str = value

        if language is not None:
            if not isinstance(language, str):
                raise TypeError("Language tag must be a string")
            if not language:
                raise ValueError("Language tag cannot be empty if provided")
            
            # Canonicalize language tag to lowercase according to RDF 1.1 spec
            canonical_lang = language.lower()
            if not BCP47_PATTERN.match(canonical_lang):
                raise ValueError(f"Invalid language tag under BCP 47: {language}")
            
            self._language: Optional[str] = canonical_lang
            self._datatype: IRI = IRI(RDF_LANG_STRING_STR)
            
            if datatype is not None and datatype != self._datatype:
                raise ValueError(
                    f"Datatype must be {RDF_LANG_STRING_STR} when language tag is specified"
                )
        else:
            self._language = None
            if datatype is None:
                self._datatype = IRI(XSD_STRING_STR)
            else:
                if not isinstance(datatype, IRI):
                    raise TypeError("Datatype must be an instance of IRI")
                if datatype.value == RDF_LANG_STRING_STR:
                    raise ValueError(
                        f"Datatype {RDF_LANG_STRING_STR} is only allowed if a language tag is provided"
                    )
                self._datatype = datatype

    @property
    def value(self) -> str:
        return self._value

    @property
    def datatype(self) -> IRI:
        return self._datatype

    @property
    def language(self) -> Optional[str]:
        return self._language

    @property
    def is_simple(self) -> bool:
        """Check if this is a simple literal (datatype is xsd:string, no language tag)."""
        return self._language is None and self._datatype.value == XSD_STRING_STR

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Literal):
            return False
        # Literal term equality (character by character for lexical form, datatype, language)
        return (
            self._value == other._value
            and self._datatype == other._datatype
            and self._language == other._language
        )

    def __hash__(self) -> int:
        return hash((Literal, self._value, self._datatype, self._language))

    def n3(self) -> str:
        # Quote and escape string according to N-Triples rules
        escaped = (
            self._value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            .replace("\b", "\\b")
            .replace("\f", "\\f")
        )
        quote_val = f'"{escaped}"'
        if self._language is not None:
            return f"{quote_val}@{self._language}"
        elif self._datatype.value == XSD_STRING_STR:
            return quote_val
        else:
            return f"{quote_val}^^{self._datatype.n3()}"


class Triple:
    """An RDF Triple consisting of subject, predicate, and object."""
    __slots__ = ("_subject", "_predicate", "_object")

    def __init__(self, subject: Union[IRI, BlankNode], predicate: IRI, object: Union[IRI, BlankNode, Literal]):
        if not isinstance(subject, (IRI, BlankNode)):
            raise TypeError("Subject must be an IRI or BlankNode")
        if not isinstance(predicate, IRI):
            raise TypeError("Predicate must be an IRI")
        if not isinstance(object, (IRI, BlankNode, Literal)):
            raise TypeError("Object must be an IRI, BlankNode, or Literal")

        self._subject = subject
        self._predicate = predicate
        self._object = object

    @property
    def subject(self) -> Union[IRI, BlankNode]:
        return self._subject

    @property
    def predicate(self) -> IRI:
        return self._predicate

    @property
    def object(self) -> Union[IRI, BlankNode, Literal]:
        return self._object

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Triple):
            return False
        return (
            self._subject == other._subject
            and self._predicate == other._predicate
            and self._object == other._object
        )

    def __hash__(self) -> int:
        return hash((Triple, self._subject, self._predicate, self._object))

    def __repr__(self) -> str:
        return f"Triple({self._subject}, {self._predicate}, {self._object})"

    def to_tuple(self) -> PyTuple[RDFTerm, IRI, RDFTerm]:
        return (self._subject, self._predicate, self._object)


class Graph:
    """An RDF Graph, which is a set of RDF Triples."""
    def __init__(self, triples: Optional[Iterable[Triple]] = None):
        self._triples: Set[Triple] = set()
        if triples is not None:
            for t in triples:
                self.add(t)

    def add(self, triple: Triple) -> None:
        if not isinstance(triple, Triple):
            raise TypeError("Can only add Triple objects to Graph")
        self._triples.add(triple)

    def remove(self, triple: Triple) -> None:
        self._triples.discard(triple)

    def __contains__(self, triple: Triple) -> bool:
        return triple in self._triples

    def __len__(self) -> int:
        return len(self._triples)

    def __iter__(self) -> Iterator[Triple]:
        return iter(self._triples)

    def triples(
        self,
        s: Optional[Union[IRI, BlankNode]] = None,
        p: Optional[IRI] = None,
        o: Optional[Union[IRI, BlankNode, Literal]] = None
    ) -> Generator[Triple, None, None]:
        """Query the graph with a triple pattern. None represents a wildcard."""
        for t in self._triples:
            if s is not None and t.subject != s:
                continue
            if p is not None and t.predicate != p:
                continue
            if o is not None and t.object != o:
                continue
            yield t

    def subjects(self, p: Optional[IRI] = None, o: Optional[Union[IRI, BlankNode, Literal]] = None) -> Generator[Union[IRI, BlankNode], None, None]:
        seen = set()
        for t in self.triples(None, p, o):
            if t.subject not in seen:
                seen.add(t.subject)
                yield t.subject

    def predicates(self, s: Optional[Union[IRI, BlankNode]] = None, o: Optional[Union[IRI, BlankNode, Literal]] = None) -> Generator[IRI, None, None]:
        seen = set()
        for t in self.triples(s, None, o):
            if t.predicate not in seen:
                seen.add(t.predicate)
                yield t.predicate

    def objects(self, s: Optional[Union[IRI, BlankNode]] = None, p: Optional[IRI] = None) -> Generator[Union[IRI, BlankNode, Literal], None, None]:
        seen = set()
        for t in self.triples(s, p, None):
            if t.object not in seen:
                seen.add(t.object)
                yield t.object

    # Set operations
    def __or__(self, other: "Graph") -> "Graph":
        if not isinstance(other, Graph):
            raise TypeError("Operand must be a Graph")
        return Graph(self._triples | other._triples)

    def __and__(self, other: "Graph") -> "Graph":
        if not isinstance(other, Graph):
            raise TypeError("Operand must be a Graph")
        return Graph(self._triples & other._triples)

    def __sub__(self, other: "Graph") -> "Graph":
        if not isinstance(other, Graph):
            raise TypeError("Operand must be a Graph")
        return Graph(self._triples - other._triples)


class Quad:
    """An RDF Quad, representing a triple inside a named graph or default graph."""
    __slots__ = ("_subject", "_predicate", "_object", "_graph_name")

    def __init__(
        self,
        subject: Union[IRI, BlankNode],
        predicate: IRI,
        object: Union[IRI, BlankNode, Literal],
        graph_name: Optional[Union[IRI, BlankNode]] = None
    ):
        if not isinstance(subject, (IRI, BlankNode)):
            raise TypeError("Subject must be an IRI or BlankNode")
        if not isinstance(predicate, IRI):
            raise TypeError("Predicate must be an IRI")
        if not isinstance(object, (IRI, BlankNode, Literal)):
            raise TypeError("Object must be an IRI, BlankNode, or Literal")
        if graph_name is not None and not isinstance(graph_name, (IRI, BlankNode)):
            raise TypeError("Graph name must be an IRI or BlankNode or None")

        self._subject = subject
        self._predicate = predicate
        self._object = object
        self._graph_name = graph_name

    @property
    def subject(self) -> Union[IRI, BlankNode]:
        return self._subject

    @property
    def predicate(self) -> IRI:
        return self._predicate

    @property
    def object(self) -> Union[IRI, BlankNode, Literal]:
        return self._object

    @property
    def graph_name(self) -> Optional[Union[IRI, BlankNode]]:
        return self._graph_name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quad):
            return False
        return (
            self._subject == other._subject
            and self._predicate == other._predicate
            and self._object == other._object
            and self._graph_name == other._graph_name
        )

    def __hash__(self) -> int:
        return hash((Quad, self._subject, self._predicate, self._object, self._graph_name))

    def __repr__(self) -> str:
        return f"Quad({self._subject}, {self._predicate}, {self._object}, {self._graph_name})"

    def to_triple(self) -> Triple:
        return Triple(self._subject, self._predicate, self._object)


# Sentinel for matching any graph in Dataset.quads
ANY = object()


class Dataset:
    """An RDF Dataset, which contains a default graph and zero or more named graphs."""
    def __init__(self):
        self._default_graph: Graph = Graph()
        self._named_graphs: Dict[Union[IRI, BlankNode], Graph] = {}

    @property
    def default_graph(self) -> Graph:
        return self._default_graph

    def get_graph(self, graph_name: Optional[Union[IRI, BlankNode]]) -> Graph:
        """Get the graph associated with graph_name (None for default graph)."""
        if graph_name is None:
            return self._default_graph
        if graph_name not in self._named_graphs:
            self._named_graphs[graph_name] = Graph()
        return self._named_graphs[graph_name]

    def add(self, quad: Quad) -> None:
        if not isinstance(quad, Quad):
            raise TypeError("Can only add Quad objects to Dataset")
        self.get_graph(quad.graph_name).add(quad.to_triple())

    def remove(self, quad: Quad) -> None:
        if not isinstance(quad, Quad):
            raise TypeError("Can only remove Quad objects from Dataset")
        if quad.graph_name is None:
            self._default_graph.remove(quad.to_triple())
        elif quad.graph_name in self._named_graphs:
            self._named_graphs[quad.graph_name].remove(quad.to_triple())
            # Clean up empty named graph if appropriate
            if len(self._named_graphs[quad.graph_name]) == 0:
                del self._named_graphs[quad.graph_name]

    def __contains__(self, quad: Quad) -> bool:
        if quad.graph_name is None:
            return quad.to_triple() in self._default_graph
        elif quad.graph_name in self._named_graphs:
            return quad.to_triple() in self._named_graphs[quad.graph_name]
        return False

    def __len__(self) -> int:
        """Total number of quads in the dataset."""
        total = len(self._default_graph)
        for g in self._named_graphs.values():
            total += len(g)
        return total

    def __iter__(self) -> Iterator[Quad]:
        """Iterate over all quads in the dataset."""
        for t in self._default_graph:
            yield Quad(t.subject, t.predicate, t.object, None)
        for name, graph in self._named_graphs.items():
            for t in graph:
                yield Quad(t.subject, t.predicate, t.object, name)

    def quads(
        self,
        s: Optional[Union[IRI, BlankNode]] = None,
        p: Optional[IRI] = None,
        o: Optional[Union[IRI, BlankNode, Literal]] = None,
        g: Optional[Union[IRI, BlankNode]] = ANY
    ) -> Generator[Quad, None, None]:
        """Query the dataset with a quad pattern. ANY matches any graph (including default).

        g=None matches only the default graph.
        g=IRI or BlankNode matches a specific named graph.
        """
        # Match default graph if g is ANY or g is None
        if g is ANY or g is None:
            for t in self._default_graph.triples(s, p, o):
                yield Quad(t.subject, t.predicate, t.object, None)

        # Match named graphs
        if g is ANY:
            for name, graph in self._named_graphs.items():
                for t in graph.triples(s, p, o):
                    yield Quad(t.subject, t.predicate, t.object, name)
        elif g is not None:
            if g in self._named_graphs:
                for t in self._named_graphs[g].triples(s, p, o):
                    yield Quad(t.subject, t.predicate, t.object, g)

    def graph_names(self) -> Iterator[Union[IRI, BlankNode]]:
        """Return an iterator over the names of all non-empty named graphs."""
        return iter(self._named_graphs.keys())

    def add_graph(self, graph_name: Union[IRI, BlankNode], graph: Optional[Graph] = None) -> None:
        """Add a named graph to the dataset."""
        if not isinstance(graph_name, (IRI, BlankNode)):
            raise TypeError("Graph name must be an IRI or BlankNode")
        if graph is None:
            self.get_graph(graph_name)
        else:
            if not isinstance(graph, Graph):
                raise TypeError("graph must be a Graph instance")
            # Copy all triples
            self._named_graphs[graph_name] = Graph(graph)

    def remove_graph(self, graph_name: Optional[Union[IRI, BlankNode]]) -> None:
        """Remove a named graph (or clear default graph if None) from the dataset."""
        if graph_name is None:
            self._default_graph = Graph()
        elif graph_name in self._named_graphs:
            del self._named_graphs[graph_name]

