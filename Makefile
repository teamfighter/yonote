.PHONY: venv install clean

venv:
	python3 -m venv .venv
	@echo "Run: source .venv/bin/activate"

install:
	pip install -e ./yonote_cli

clean:
	rm -rf **/__pycache__ *.egg-info build dist

