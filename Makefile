.PHONY: venv install clean build

venv:
	python3 -m venv .venv
	@echo "Run: source .venv/bin/activate"

install:
	pip install -e ./yonote_cli

clean:
	rm -rf **/__pycache__ *.egg-info build dist

build:
	docker run --rm -v "$(PWD)":/src -w /src python:3.11-slim-bullseye \
	        bash -c "apt-get update && apt-get install -y binutils && \
	                       pip install -r requirements.txt && \
	                       pyinstaller yonote_cli/yonote_cli/__main__.py --name yonote --onefile --collect-all InquirerPy"
