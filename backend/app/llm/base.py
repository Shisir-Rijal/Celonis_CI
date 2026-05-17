"""Abstract base classes for LLM clients.

Two interfaces, intentionally separated:
- ChatClient — for providers that can generate text from messages
- EmbeddingClient — for providers that can turn text into vectors

A concrete provider implements whichever it supports. OpenAI implements
both. Perplexity (when added) only implements ChatClient. This avoids
NotImplementedError stubs on subclasses for capabilities they cannot offer.

Vision is not a separate method. Image inputs are passed as part of the
message content in `complete()`, matching how modern LLM APIs work.
"""

from abc import ABC, abstractmethod


class ChatClient(ABC):
    """Contract for any provider that can generate a text response from messages."""

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages to the model and return the generated text.

        Args:
            messages: List of message dicts in the OpenAI format:
                [{"role": "system" | "user" | "assistant", "content": "..."}]
                For vision inputs, content can be a list of parts:
                [{"type": "text", "text": "..."},
                 {"type": "image_url", "image_url": {"url": "..."}}]
            **kwargs: Provider-specific options (model, temperature, max_tokens, ...).

        Returns:
            The model's reply as a plain string.

        Raises:
            LLMProviderError: If the call fails after all retries.
        """


class EmbeddingClient(ABC):
    """Contract for any provider that can turn text into embedding vectors."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return one vector per input.

        Args:
            texts: List of input strings to embed.

        Returns:
            A list of embedding vectors, one per input, in the same order.
            Vector length is provider/model specific (1536 for
            text-embedding-3-small).

        Raises:
            EmbeddingError: If the call fails after all retries.
        """
