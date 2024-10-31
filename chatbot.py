import getpass
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Sequence
from langchain_core.messages import SystemMessage, trim_messages

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
import logging
from transformers import logging as transformers_logging
logging.basicConfig(level=logging.ERROR)
transformers_logging.set_verbosity_error()

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

model = ChatGroq(model="llama3-8b-8192")


class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    language: str


# workflow = StateGraph(state_schema=MessagesState)

workflow = StateGraph(state_schema=State)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability in {language}.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

trimmer = trim_messages(
    max_tokens=3000,
    strategy="last",
    token_counter=model,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

# Model calling function
def call_model(state: State):
    chain = prompt | model
    trimmed_messages= trimmer.invoke(state["messages"])
    response = chain.invoke(
        {"messages": trimmed_messages, "language": state["language"]}
    )
    return {"messages": [response]}


workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

# Add memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "abc346"}}

language = "English" 

while True:
    query = input("Ask: ")
    input_messages = [HumanMessage(content=query)]
    for chunk, metadata in app.stream(
        {"messages": input_messages, "language": language},
        config,
        stream_mode="messages",
        ):
        if isinstance(chunk, AIMessage): 
            print(chunk.content, end="")
