

```sh
$ uv init . [--app | --lib]
$ uv add fastapi requests uvicorn
$ source deactivate
$ source .venv/bin/activate
$ uvicorn aihub.main:app --reload

$ uv sync

$ uv remove flask

$ uvicorn aihub.app:app --reload --host 0.0.0.0 --port 8000
```

[OpenAPI Docs](http://localhost:8000/docs)