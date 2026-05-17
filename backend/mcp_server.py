import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

from app.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
