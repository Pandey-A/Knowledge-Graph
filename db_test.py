import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class KnowledgeGraph:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
        self.database = os.getenv("NEO4J_DATABASE")

    def close(self):
        self.driver.close()

    def create_test_node(self, name):
        with self.driver.session(database=self.database) as session:
            session.run("CREATE (p:Person {name: $name})", name=name)
            print(f"Success: Created node for {name}")


if __name__ == "__main__":
    kg = KnowledgeGraph()
    kg.create_test_node("Test Professor")
    kg.close()
