from langchain_core.language_models.fake_chat_models import FakeListChatModel

def get_fake_llm(responses: list[str]) -> FakeListChatModel:
    """Returns a FakeListChatModel preloaded with responses for testing."""
    return FakeListChatModel(responses=responses)
