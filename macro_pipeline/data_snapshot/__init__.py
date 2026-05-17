"""L11 frozen data snapshot — bundled with the web app + PyInstaller exe.

Populated by ``scripts/build_data_snapshot.py`` from the developer's
``data/cache/`` directory. The snapshot enables the L11 ProducerAdapter
to derive ForecastInputs from real historical panels instead of L10's
heuristic modulators around canonical defaults.

See ``docs/build-plans/L11_PRODUCER_INTEGRATION_AUDIT.md`` for the panel
selection rationale + form-to-panel overlay mapping.
"""
