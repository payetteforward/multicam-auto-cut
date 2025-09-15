.PHONY: help install install-dev test clean format lint run

help:
	@echo "Available commands:"
	@echo "  make install      Install the package"
	@echo "  make install-dev  Install with development dependencies"
	@echo "  make test        Run tests"
	@echo "  make clean       Clean temporary files"
	@echo "  make format      Format code with black"
	@echo "  make lint        Run linting checks"
	@echo "  make run         Run the CLI with test file"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf temp/* outputs/* transcripts/* 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov 2>/dev/null || true

format:
	black src/ tests/ --line-length 88

lint:
	flake8 src/ tests/ --max-line-length 88
	mypy src/ --ignore-missing-imports

run:
	@if [ -f "src/fcpxml_exports/ios 26 off.fcpxmld/Info.fcpxml" ]; then \
		python autocut.py "src/fcpxml_exports/ios 26 off.fcpxmld/Info.fcpxml"; \
	else \
		echo "Test file not found. Please provide an FCPXML file."; \
	fi