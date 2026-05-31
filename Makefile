.PHONY: test format lint typecheck check coverage clean

test:
	uv run pytest

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run pyright src/

check: format lint typecheck test

coverage:
	uv run pytest --cov=src/outreach --cov-report=term --cov-report=html

clean:
	rm -rf .venv/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf *.egg-info/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -delete
