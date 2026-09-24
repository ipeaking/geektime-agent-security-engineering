.PHONY: lab-normal lab-attack lab-attack-replay lab-attack-live test clean

PYTHON ?= python
PYTHONPATH := src

lab-normal:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case normal

lab-attack:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case attack --provider replay

lab-attack-replay: lab-attack

lab-attack-live:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m agent_security.lab.runner --case attack --provider deepseek

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; p=Path('.lab-output'); shutil.rmtree(p) if p.exists() else None"
