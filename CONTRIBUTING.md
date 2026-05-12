# Contributing to EPL (English Programming Language)

First off, thank you for considering contributing to EPL! It's people like you that make EPL such a great language.

## 1. Code of Conduct
This project and everyone participating in it is governed by the [EPL Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## 2. Contributor License Agreement (CLA)
Before we can merge your Pull Request, you **must** sign the Contributor License Agreement transferring copyright to Abneesh Singh. A bot will automatically prompt you to do this when you open your first PR.

## 3. Local Development Setup
EPL requires Python 3.9+. 

```bash
git clone https://github.com/abneeshsingh21/EPL.git
cd EPL
pip install -e .[dev,cloud]
```

## 4. Code Formatting (Ruff)
EPL uses `ruff` to enforce a strict coding style. **Do not** submit a PR with messy code.

Before committing, run:
```bash
ruff format .
ruff check --fix .
```

## 5. Testing Requirements
We require **100% test passing** before merging. If you add a new feature, you **must** write tests for it in the `tests/` directory.

To run the tests locally:
```bash
pytest tests/
```

## 6. Pull Request Process
1. Ensure your code is formatted with Ruff.
2. Ensure all tests pass.
3. Update the `CHANGELOG.md` with details of your changes.
4. Open your PR and fill out the checklist in the PR template.
5. Sign the CLA when the bot prompts you.

Thank you for helping build the future of English Programming!
