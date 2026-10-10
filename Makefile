.PHONY: lab-normal lab-attack lab-attack-replay lab-attack-live threat-model-validate threat-model-render threat-model-check context-lab-inspect context-lab-render context-lab-check context-lab-live context-lab-report carrier-lab-inspect carrier-lab-render carrier-lab-check carrier-lab-live carrier-lab-report lesson-02 lesson-03 lesson-04 test clean

PYTHON ?= python
PYTHONPATH := src
THREAT_MODEL_DIR := labs/lesson_02_threat_model/model
THREAT_MODEL_REPORT := labs/lesson_02_threat_model/generated/threat_model_report.md
CONTEXT_LAB_CASES := labs/lesson_03_prompt_injection_mechanism/cases
CONTEXT_LAB_GENERATED := labs/lesson_03_prompt_injection_mechanism/generated
CONTEXT_LAB_OUTPUT := .lab-output/lesson-03
CARRIER_LAB_CASES := labs/lesson_04_indirect_prompt_injection/cases
CARRIER_LAB_GENERATED := labs/lesson_04_indirect_prompt_injection/generated
CARRIER_LAB_OUTPUT := .lab-output/lesson-04

lab-normal:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case normal

lab-attack:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case attack --provider replay

lab-attack-replay: lab-attack

lab-attack-live:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case attack --provider deepseek

threat-model-validate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.threat_model validate --model-dir $(THREAT_MODEL_DIR) --repository-root .

threat-model-render:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.threat_model render --model-dir $(THREAT_MODEL_DIR) --output-file $(THREAT_MODEL_REPORT) --repository-root .

threat-model-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.threat_model check --model-dir $(THREAT_MODEL_DIR) --output-file $(THREAT_MODEL_REPORT) --repository-root .

context-lab-inspect:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.context_lab inspect --cases-dir $(CONTEXT_LAB_CASES)

context-lab-render:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.context_lab render --cases-dir $(CONTEXT_LAB_CASES) --output-dir $(CONTEXT_LAB_GENERATED)

context-lab-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.context_lab check --cases-dir $(CONTEXT_LAB_CASES) --output-dir $(CONTEXT_LAB_GENERATED)

context-lab-live:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.context_lab live --cases-dir $(CONTEXT_LAB_CASES) --output-dir $(CONTEXT_LAB_OUTPUT) --repeat 3

context-lab-report:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.context_lab report --cases-dir $(CONTEXT_LAB_CASES) --input $(CONTEXT_LAB_OUTPUT)/live_runs.jsonl --output-dir $(CONTEXT_LAB_OUTPUT)

carrier-lab-inspect:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.indirect_lab inspect --cases-dir $(CARRIER_LAB_CASES)

carrier-lab-render:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.indirect_lab render --cases-dir $(CARRIER_LAB_CASES) --output-dir $(CARRIER_LAB_GENERATED)

carrier-lab-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.indirect_lab check --cases-dir $(CARRIER_LAB_CASES) --output-dir $(CARRIER_LAB_GENERATED)

carrier-lab-live:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.indirect_lab live --cases-dir $(CARRIER_LAB_CASES) --output-dir $(CARRIER_LAB_OUTPUT) --repeat 3

carrier-lab-report:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.indirect_lab report --cases-dir $(CARRIER_LAB_CASES) --input $(CARRIER_LAB_OUTPUT)/live_runs.jsonl --output-dir $(CARRIER_LAB_OUTPUT)

lesson-02: threat-model-validate threat-model-check test

lesson-03: context-lab-inspect context-lab-check test

lesson-04: carrier-lab-inspect carrier-lab-check test

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; p=Path('.lab-output'); shutil.rmtree(p) if p.exists() else None"
