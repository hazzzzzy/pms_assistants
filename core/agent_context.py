from fastapi import FastAPI


class AgentContext:
    def __init__(self, app: FastAPI, include_graph: bool):
        self.mysql_engine = app.state.mysql_engine
        self.vs_schema = app.state.vs_schema
        self.vs_qa = app.state.vs_qa
        self.graph = app.state.graph if include_graph else None
