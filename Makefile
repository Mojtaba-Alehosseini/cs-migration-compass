# CS Migration Compass
# One command reruns the whole data pipeline from scratch; one command builds the site.

PY ?= python
NPM ?= npm

.PHONY: help setup pipeline pipeline-fresh validate audit test docs site-dev site-build site-preview clean all postings

help:
	@echo "CS Migration Compass"
	@echo ""
	@echo "  make setup           install Python + Node dependencies"
	@echo "  make pipeline        run every data source (cached downloads reused)"
	@echo "  make pipeline-fresh  clear data/raw and re-download everything"
	@echo "  make validate        run the data validation gate (CI runs this)"
	@echo "  make audit           run Tier-1 structural invariants (scripts/audit_data.py)"
	@echo "                       — complements validate, see that file's own docstring"
	@echo "  make postings        re-run every postings harvester AND the merge, in order"
	@echo "                       — package 14: a harvester run outside this target is how the"
	@echo "                       merge went stale last time; use this, not the individual scripts"
	@echo "  make reconcile       run Tier-2 live-source reconciliation (hits the network)"
	@echo "  make snapshot        run Tier-3 drift + coverage snapshot"
	@echo "  make test            run the regression suite (scripts/tests/) — UI half"
	@echo "                       needs 'make site-build && make site-preview' running"
	@echo "  make docs            regenerate docs/SOURCES.md and docs/DATA-QUALITY.md"
	@echo "  make site-dev        start the Vite dev server"
	@echo "  make site-build      production build of the site"
	@echo "  make all             pipeline + validate + docs + site-build"
	@echo ""
	@echo "  Run one source:      $(PY) scripts/pipeline.py world_bank"
	@echo "  List sources:        $(PY) scripts/pipeline.py --list"

setup:
	$(PY) -m pip install -r scripts/requirements.txt
	cd site && $(NPM) install

pipeline:
	$(PY) scripts/pipeline.py

pipeline-fresh:
	rm -rf data/raw
	$(PY) scripts/pipeline.py

validate:
	$(PY) scripts/validate_data.py

audit:
	$(PY) scripts/audit_data.py

postings:
	$(PY) scripts/src_postings_ashby.py
	$(PY) scripts/src_postings_greenhouse.py
	$(PY) scripts/src_postings_lever.py
	$(PY) scripts/src_postings_teamtailor.py
	$(PY) scripts/src_postings_usajobs.py
	$(PY) scripts/src_postings_hn.py
	$(PY) scripts/build_postings.py
	$(PY) scripts/build_site_data.py

reconcile:
	$(PY) scripts/reconcile.py

snapshot:
	$(PY) scripts/snapshot_stats.py

test:
	$(PY) scripts/tests/run_all.py

docs:
	$(PY) scripts/generate_sources_doc.py
	$(PY) scripts/generate_data_quality_doc.py

site-dev:
	cd site && $(NPM) run dev

site-build:
	cd site && $(NPM) run build

site-preview:
	cd site && $(NPM) run preview

clean:
	rm -rf site/dist site/node_modules

all: pipeline validate docs site-build
