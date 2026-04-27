# EasyEscrow Backend

## Tests

The project uses `pytest`, `pytest-django`, DRF `APIClient`, and `factory_boy`.
Pytest is configured in `pytest.ini` to use `easyescrow_1.settings.test_sqlite`.

Run all tests:

```bash
./.venv/bin/python -m pytest
```

Run one app's tests:

```bash
./.venv/bin/python -m pytest backend/transactions/tests
./.venv/bin/python -m pytest backend/accounts/tests
```

Run one test file:

```bash
./.venv/bin/python -m pytest backend/transactions/tests/test_week3_workflows.py
```

Run one specific test:

```bash
./.venv/bin/python -m pytest backend/transactions/tests/test_week3_workflows.py::test_happy_path_transaction_invitation_workflow
```

The Week 3 workflow tests exercise the real DRF routes for transaction creation,
buyer/seller invitations, invitation acceptance, permission rejection for
non-brokers, expired invitation handling, wrong-user invitation acceptance,
duplicate invitation rejection, and unauthorized transaction reads.

Account negative-path tests cover invalid identity and broker application API
payloads plus reviewer permission failures on the current admin review actions.
The documents test currently verifies the Week 4 model relationship; document
API workflow tests should be added when document endpoints exist.
