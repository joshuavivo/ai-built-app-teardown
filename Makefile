# Standard-library Python; no install step. `make test` is the proof.
.PHONY: test before after

test:    ## run every exploit against before/after and the customer-still-works checks
	python3 -W error::ResourceWarning -m unittest discover -s tests -v

before:  ## run the vulnerable app on http://127.0.0.1:8000 (local only)
	python3 before.py

after:   ## run the fixed app on http://127.0.0.1:8001 (local only)
	python3 after.py
