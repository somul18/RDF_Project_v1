import sys
import os
# Add the 'src' directory to the python path so imports resolve from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.rdf import RDFDataset, RDFNamespace
from rdf.namespaces import RDF

dataset = RDFDataset()

# Bind namespaces on dataset
dataset.bind(RDFNamespace("ex", "http://example.org/"))
dataset.bind(RDF)

# Get the graphs
default = dataset.default_graph()
graph = dataset.graph("people")
cities = dataset.graph("cities")

# Fluent builder usage
graph.person("Marie_Curie") \
     .type("Scientist") \
     .born_in("Warsaw") \
     .birth_year(1867)

# Print dataset serialization as N-Quads
print("--- N-Quads Serialization ---")
print(dataset.serialize("nquads"))

# Print the specific 'people' graph serialization as Turtle
print("--- 'people' Graph Turtle Serialization ---")
print(graph.serialize("turtle"))
