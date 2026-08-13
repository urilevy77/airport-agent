"""HTTP layer for the Airport Investment Intelligence Agent."""
from fastapi import FastAPI


def create_app(conversation_factory=None):
    """Build the app. `conversation_factory` is injectable so tests can run the
    whole endpoint without an OpenAI key or a network call."""
    app = FastAPI(title="Airport Investment Intelligence Agent")

    @app.get("/health")
    def health():
        """Render polls this to decide whether the container is alive."""
        return {"ok": True}

    return app


app = create_app()
