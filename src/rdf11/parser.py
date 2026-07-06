from typing import Union, IO, Optional
from .model import IRI, BlankNode, Literal, Triple, Quad, Graph, Dataset


class LineParser:
    def __init__(self, line: str, line_num: int):
        self.line = line
        self.line_num = line_num
        self.index = 0
        self.length = len(line)

    def error(self, msg: str):
        raise ValueError(f"{msg} at index {self.index}")

    def skip_whitespace(self):
        while self.index < self.length and self.line[self.index] in " \t":
            self.index += 1

    def peek(self) -> Optional[str]:
        if self.index < self.length:
            return self.line[self.index]
        return None

    def read_char(self) -> str:
        if self.index >= self.length:
            self.error("Unexpected end of line")
        char = self.line[self.index]
        self.index += 1
        return char

    def parse_iri(self) -> IRI:
        if self.peek() != '<':
            self.error("Expected '<' at start of IRI")
        self.read_char()  # consume '<'
        
        iri_chars = []
        while True:
            char = self.peek()
            if char is None:
                self.error("Unterminated IRI")
            if char == '>':
                self.read_char()
                break
            if char == '\\':
                self.read_char()  # consume '\\'
                esc_type = self.peek()
                if esc_type is None:
                    self.error("Trailing backslash in IRI")
                if esc_type in ('u', 'U'):
                    num_chars = 4 if esc_type == 'u' else 8
                    self.read_char()  # consume u/U
                    hex_str = "".join(self.read_char() for _ in range(num_chars))
                    try:
                        iri_chars.append(chr(int(hex_str, 16)))
                    except ValueError as e:
                        self.error(f"Invalid unicode escape: \\{esc_type}{hex_str}")
                elif esc_type == '\\':
                    iri_chars.append('\\')
                    self.read_char()
                elif esc_type == '>':
                    iri_chars.append('>')
                    self.read_char()
                else:
                    self.error(f"Invalid escape in IRI: \\{esc_type}")
            else:
                if char in " \t<>\"{}|^`\\":
                    self.error(f"Invalid character in IRI: {char}")
                iri_chars.append(self.read_char())
        
        return IRI("".join(iri_chars))

    def parse_blank_node(self) -> BlankNode:
        if not self.line[self.index:].startswith('_:'):
            self.error("Expected '_:' at start of Blank Node")
        self.index += 2  # consume '_:'
        start = self.index
        
        while self.index < self.length:
            char = self.line[self.index]
            if char in " \t.#\r\n":
                break
            self.index += 1
        
        label = self.line[start:self.index]
        if not label:
            self.error("Empty blank node label")
        
        # W3C blank node grammar: cannot end with a dot
        if label.endswith('.'):
            self.index -= 1
            label = label[:-1]
            if not label:
                self.error("Empty blank node label")
        
        return BlankNode(label)

    def parse_literal(self) -> Literal:
        if self.peek() != '"':
            self.error("Expected '\"' at start of Literal")
        self.read_char()  # consume '"'
        
        lit_chars = []
        while True:
            char = self.peek()
            if char is None:
                self.error("Unterminated Literal")
            if char == '"':
                self.read_char()
                break
            if char in ('\n', '\r'):
                self.error("Raw newline not allowed in literal")
            if char == '\\':
                self.read_char()  # consume '\\'
                esc = self.peek()
                if esc is None:
                    self.error("Trailing backslash in literal")
                if esc == 't':
                    lit_chars.append('\t')
                    self.read_char()
                elif esc == 'b':
                    lit_chars.append('\b')
                    self.read_char()
                elif esc == 'n':
                    lit_chars.append('\n')
                    self.read_char()
                elif esc == 'r':
                    lit_chars.append('\r')
                    self.read_char()
                elif esc == 'f':
                    lit_chars.append('\f')
                    self.read_char()
                elif esc == '"':
                    lit_chars.append('"')
                    self.read_char()
                elif esc == "'":
                    lit_chars.append("'")
                    self.read_char()
                elif esc == '\\':
                    lit_chars.append('\\')
                    self.read_char()
                elif esc in ('u', 'U'):
                    num_chars = 4 if esc == 'u' else 8
                    self.read_char()  # consume u/U
                    hex_str = "".join(self.read_char() for _ in range(num_chars))
                    try:
                        lit_chars.append(chr(int(hex_str, 16)))
                    except ValueError as e:
                        self.error(f"Invalid unicode escape: \\{esc}{hex_str}")
                else:
                    self.error(f"Invalid escape sequence: \\{esc}")
            else:
                lit_chars.append(self.read_char())
        
        lexical_form = "".join(lit_chars)
        
        lang = None
        datatype = None
        
        if self.peek() == '@':
            self.read_char()  # consume '@'
            start = self.index
            while self.index < self.length:
                char = self.line[self.index]
                if not (char.isalpha() or char == '-'):
                    break
                self.index += 1
            lang = self.line[start:self.index]
            if not lang:
                self.error("Expected language tag after '@'")
        elif self.line[self.index:].startswith('^^'):
            self.index += 2  # consume '^^'
            datatype = self.parse_iri()
            
        return Literal(lexical_form, datatype=datatype, language=lang)

    def parse_triple_line(self) -> Optional[Triple]:
        self.skip_whitespace()
        if self.peek() is None or self.peek() == '#':
            return None
            
        subject = None
        if self.peek() == '<':
            subject = self.parse_iri()
        elif self.line[self.index:].startswith('_:'):
            subject = self.parse_blank_node()
        else:
            self.error("Expected subject (IRI or Blank Node)")
            
        self.skip_whitespace()
        predicate = None
        if self.peek() == '<':
            predicate = self.parse_iri()
        else:
            self.error("Expected predicate (IRI)")
            
        self.skip_whitespace()
        obj = None
        if self.peek() == '<':
            obj = self.parse_iri()
        elif self.line[self.index:].startswith('_:'):
            obj = self.parse_blank_node()
        elif self.peek() == '"':
            obj = self.parse_literal()
        else:
            self.error("Expected object (IRI, Blank Node, or Literal)")
            
        self.skip_whitespace()
        if self.peek() != '.':
            self.error("Expected '.' at end of triple")
        self.read_char()  # consume '.'
            
        self.skip_whitespace()
        if self.peek() is not None and self.peek() != '#':
            self.error("Unexpected content after '.'")
            
        return Triple(subject, predicate, obj)

    def parse_quad_line(self) -> Optional[Quad]:
        self.skip_whitespace()
        if self.peek() is None or self.peek() == '#':
            return None
            
        subject = None
        if self.peek() == '<':
            subject = self.parse_iri()
        elif self.line[self.index:].startswith('_:'):
            subject = self.parse_blank_node()
        else:
            self.error("Expected subject (IRI or Blank Node)")
            
        self.skip_whitespace()
        predicate = None
        if self.peek() == '<':
            predicate = self.parse_iri()
        else:
            self.error("Expected predicate (IRI)")
            
        self.skip_whitespace()
        obj = None
        if self.peek() == '<':
            obj = self.parse_iri()
        elif self.line[self.index:].startswith('_:'):
            obj = self.parse_blank_node()
        elif self.peek() == '"':
            obj = self.parse_literal()
        else:
            self.error("Expected object (IRI, Blank Node, or Literal)")
            
        self.skip_whitespace()
        
        # Now we could have a graph name OR a dot.
        graph_name = None
        next_char = self.peek()
        if next_char == '<':
            graph_name = self.parse_iri()
            self.skip_whitespace()
        elif self.line[self.index:].startswith('_:'):
            graph_name = self.parse_blank_node()
            self.skip_whitespace()
            
        if self.peek() != '.':
            self.error("Expected '.' at end of quad")
        self.read_char()  # consume '.'
            
        self.skip_whitespace()
        if self.peek() is not None and self.peek() != '#':
            self.error("Unexpected content after '.'")
            
        return Quad(subject, predicate, obj, graph_name)


def parse_n_triples(stream_or_str: Union[IO[str], str]) -> Graph:
    graph = Graph()
    
    if isinstance(stream_or_str, str):
        lines = stream_or_str.splitlines()
    else:
        # Check if it's an iterable of lines
        lines = stream_or_str
        
    for line_num, line in enumerate(lines, 1):
        line = line.rstrip('\r\n')
        parser = LineParser(line, line_num)
        try:
            triple = parser.parse_triple_line()
            if triple is not None:
                graph.add(triple)
        except Exception as e:
            raise ValueError(f"Parsing error on line {line_num}: {e}") from e
            
    return graph


def parse_n_quads(stream_or_str: Union[IO[str], str]) -> Dataset:
    dataset = Dataset()
    
    if isinstance(stream_or_str, str):
        lines = stream_or_str.splitlines()
    else:
        lines = stream_or_str
        
    for line_num, line in enumerate(lines, 1):
        line = line.rstrip('\r\n')
        parser = LineParser(line, line_num)
        try:
            quad = parser.parse_quad_line()
            if quad is not None:
                dataset.add(quad)
        except Exception as e:
            raise ValueError(f"Parsing error on line {line_num}: {e}") from e
            
    return dataset
