RelayDon
========

> Relay: noun, electrical device such that current flowing through it in one circuit can switch on and off a current in a second circuit.

Relay reads the RSS feeds from the file and posts to Mastodon new posts.

Running Locally
---------------

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Create `.env` file from `.env.example` and fill with desired
2. Create a `data.csv` file from `example.data.csv` filling it with the RSS feeds, one feed per line
4. Run `uv run relay.py`

Running in Docker
-----------------

```bash
docker run --rm -it -v ./data.csv:/app/data.csv -v ./.env:/app/.env ghcr.io/paulchubatyy/paulchubatyy/relaydon:latest
```
