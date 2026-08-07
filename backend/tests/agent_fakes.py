"""Test doubles for the agent brain: no real API calls, ever."""


class FakeLlm:
    """Returns queued responses and records every prompt it receives."""

    def __init__(self) -> None:
        self.daily_responses: list[str] = []
        self.retro_responses: list[str] = []
        self.daily_prompts: list[str] = []
        self.retro_prompts: list[str] = []

    def queue_daily(self, response: str) -> None:
        self.daily_responses.append(response)

    def queue_retro(self, response: str) -> None:
        self.retro_responses.append(response)

    def complete_daily(self, prompt: str) -> str:
        self.daily_prompts.append(prompt)
        if not self.daily_responses:
            raise AssertionError("FakeLlm has no queued daily response")
        return self.daily_responses.pop(0)

    def complete_retro(self, prompt: str) -> str:
        self.retro_prompts.append(prompt)
        if not self.retro_responses:
            raise AssertionError("FakeLlm has no queued retro response")
        return self.retro_responses.pop(0)
