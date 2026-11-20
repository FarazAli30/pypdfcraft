.PHONY: help native bindings catalog oneshot docs test test-engine wheel clean
LIB ?= rust/target/release/$(shell python -c "import sys;print('pdfcraft_android.dll' if sys.platform=='win32' else 'libpdfcraft_android.dylib' if sys.platform=='darwin' else 'libpdfcraft_android.so')")
TAG ?= manylinux_2_28_x86_64

help:
	@echo "native | bindings | catalog | oneshot | docs | test | test-engine | wheel TAG=<platform tag> | clean"

native:        ## build the engine for this machine
	cd rust && cargo build --release --locked -p pdfcraft-android

bindings:      ## regenerate src/pypdfcraft/_bindings.py from the built library
	python scripts/gen_bindings.py $(LIB)

catalog:       ## snapshot of the engine's tool table
	PDFCRAFT_LIB=$(LIB) python -m pypdfcraft catalog --json src/pypdfcraft/data/tools_catalog.json

oneshot:       ## typed one-call module for every tool
	python scripts/gen_oneshot.py

docs:          ## generated reference pages + site
	python scripts/gen_docs.py && mkdocs build --strict

test:          ## unit tests (no native library needed)
	pytest -m "not engine"

test-engine:   ## everything, against the real library
	PDFCRAFT_LIB=$(LIB) pytest

wheel:         ## platform wheel from the built library
	python scripts/build_wheel.py --lib $(LIB) --tag $(TAG) --out dist

clean:
	rm -rf dist site build *.egg-info
