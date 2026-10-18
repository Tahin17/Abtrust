install:
	pip install -e ".[dev]"

lint:
	ruff check src tests scripts app
	ruff format --check src tests scripts app

test:
	pytest -q

validate:
	abtrust validate --out reports

case-study:
	python scripts/case_study.py

hillstrom:
	python scripts/hillstrom.py

app:
	streamlit run app/streamlit_app.py

.PHONY: install lint test validate case-study hillstrom app
