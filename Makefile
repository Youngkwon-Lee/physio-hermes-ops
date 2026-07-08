.PHONY: check pre-commit secret-scan test

check: secret-scan test

pre-commit:
	uv run pre-commit run --all-files

secret-scan:
	uv run pre-commit run gitleaks --all-files

test:
	uv run pytest
