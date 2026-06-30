import sys
sys.path.insert(0, r'C:\Users\chsan\hermes\brain')
from rag.graph import KnowledgeGraph
from config import VAULT_PATH
graph = KnowledgeGraph(VAULT_PATH)
result = graph.build_graph()
print(f'Grafo: {result["nodes"]} nodos, {result["edges"]} conexiones')
