import httpx

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text"
BATCH_SIZE = 10
TIMEOUT = 60.0


class OllamaError(Exception):
    pass


async def check_ollama(ollama_url: str = DEFAULT_OLLAMA_URL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(ollama_url)
            return resp.status_code == 200
    except httpx.ConnectError:
        return False


async def embed_texts(
    texts: list[str],
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    on_batch_done: callable = None,
) -> list[list[float]]:
    if not texts:
        return []

    url = f"{ollama_url}/api/embed"
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]

            try:
                resp = await client.post(url, json={
                    "model": model,
                    "input": batch,
                })
            except httpx.ConnectError:
                raise OllamaError(
                    "Cannot connect to Ollama. "
                    "Start it with: ollama serve"
                )
            except httpx.TimeoutException:
                raise OllamaError(
                    f"Ollama timed out after {TIMEOUT}s. "
                    "Try a smaller batch or check Ollama status."
                )

            if resp.status_code == 404:
                raise OllamaError(
                    f"Model '{model}' not found. "
                    f"Pull it with: ollama pull {model}"
                )

            if resp.status_code != 200:
                raise OllamaError(
                    f"Ollama error {resp.status_code}: {resp.text[:200]}"
                )

            data = resp.json()
            embeddings = data.get("embeddings", [])

            if len(embeddings) != len(batch):
                raise OllamaError(
                    f"Expected {len(batch)} embeddings, got {len(embeddings)}"
                )

            all_embeddings.extend(embeddings)

            if on_batch_done:
                on_batch_done(len(batch))

    return all_embeddings


async def embed_single(
    text: str,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> list[float]:
    result = await embed_texts([text], model=model, ollama_url=ollama_url)
    return result[0]
