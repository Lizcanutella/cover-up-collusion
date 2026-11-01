"""Message state. In-memory for now; the Postgres store is COMMS-640."""

import threading

from comms.models import DeliveryStatus, Message


class InMemoryStore:
    def __init__(self):
        self._messages: dict[str, Message] = {}
        self._by_provider_id: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def add(self, message: Message) -> Message:
        with self._lock:
            self._messages[message.id] = message
            if message.provider and message.provider_message_id:
                self._by_provider_id[(message.provider, message.provider_message_id)] = message.id
        return message

    def get(self, message_id: str) -> Message | None:
        return self._messages.get(message_id)

    def find_by_provider_id(self, provider: str, provider_message_id: str) -> Message | None:
        message_id = self._by_provider_id.get((provider, provider_message_id))
        return self._messages.get(message_id) if message_id else None

    def link_provider(self, message: Message, provider: str, provider_message_id: str) -> None:
        with self._lock:
            message.provider, message.provider_message_id = provider, provider_message_id
            self._by_provider_id[(provider, provider_message_id)] = message.id

    def set_status(self, message: Message, status: DeliveryStatus, detail: str = "") -> None:
        with self._lock:
            message.status = status
            message.history.append((str(status), detail))

    def __len__(self) -> int:
        return len(self._messages)
