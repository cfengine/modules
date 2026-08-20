.PHONY: check lint format all clean tools

all: tools clean lint format check

tools:
	sudo pipx install --global flake8 pyright black pyflakes pytest cfbs cfengine
	echo "deploy test requires cf-agent installed..."
	command -v cf-agent

clean:
	rm -rf tests/deploy/out

lint: clean tools
	cfbs status
	cfbs validate
	cfbs --check pretty ./cfbs.json
	./ci/linting.sh
	cfengine lint --strict no ./

format: lint
	cfengine format --check

check: format
	pytest promise-types/ -v
	bash tests/deploy/test.sh
