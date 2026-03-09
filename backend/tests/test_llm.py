import pytest
import httpx

from app.services.llm import (
    GenerateOptions,
    MockLLMClient,
    OllamaLLMClient,
    get_llm_client,
)


def test_ollama_success_returns_content():
    payload = {"choices": [{"message": {"content": "Hello"}}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/v1/chat/completions" in str(request.url)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = OllamaLLMClient("http://localhost:11434", "llama3", transport=transport)
    out = client.generate([{"role": "user", "content": "Hi"}])
    assert out == "Hello"


def test_ollama_request_body_model_and_messages():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "x"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OllamaLLMClient("http://localhost:11434", "llama3", transport=transport)
    client.generate(
        [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hi"}],
        options=GenerateOptions(temperature=0.5),
    )
    body = seen["body"]
    assert body["model"] == "llama3"
    assert body["messages"] == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    assert body["temperature"] == 0.5


def test_ollama_json_mode_sends_response_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"key": "value"}'}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OllamaLLMClient("http://localhost:11434", "llama3", transport=transport)
    out = client.generate(
        [{"role": "user", "content": "Return JSON"}],
        options=GenerateOptions(json_mode=True),
    )
    assert seen["body"].get("response_format") == {"type": "json_object"}
    assert out == '{"key": "value"}'


def test_ollama_options_model_override():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    transport = httpx.MockTransport(handler)
    client = OllamaLLMClient("http://localhost:11434", "llama3", transport=transport)
    client.generate(
        [{"role": "user", "content": "Hi"}],
        options=GenerateOptions(model="custom-model"),
    )
    assert seen["body"]["model"] == "custom-model"


def test_ollama_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Server error")

    transport = httpx.MockTransport(handler)
    client = OllamaLLMClient("http://localhost:11434", "llama3", transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        client.generate([{"role": "user", "content": "Hi"}])


def test_mock_llm_returns_configured_string():
    client = MockLLMClient(response="Fixed reply")
    out = client.generate([{"role": "user", "content": "Anything"}])
    assert out == "Fixed reply"


def test_mock_llm_default_response():
    client = MockLLMClient()
    out = client.generate([{"role": "user", "content": "Hi"}])
    assert out == "Mock LLM response"


def test_get_llm_client_returns_ollama_client():
    client = get_llm_client()
    assert isinstance(client, OllamaLLMClient)
