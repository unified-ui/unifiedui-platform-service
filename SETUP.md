

```sh
$ uv init . [--app | --lib]
$ uv add fastapi requests uvicorn
$ source deactivate
$ source .venv/bin/activate
$ uvicorn unifiedui.main:app --reload

$ uv sync

$ uv remove flask

$ uvicorn unifiedui.app:app --reload --host 0.0.0.0 --port 8000

$ pytest tests/api/v1/tenants.py -v
source .venv/bin/activate

pytest -v
pytest tests/ -n auto
```

[OpenAPI Docs](http://localhost:8000/docs)
