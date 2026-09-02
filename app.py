from app import create_app
import os


app = create_app()


if __name__ == "__main__":
    host = os.getenv("AYAMPI_DEV_HOST", os.getenv("ATLAS_HOST", "127.0.0.1"))
    port = int(os.getenv("AYAMPI_DEV_LENS_PORT", os.getenv("ATLAS_PORT", "5101")))
    debug = os.getenv("ATLAS_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug)
