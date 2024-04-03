# Chroma Basic Authorization Model with OpenFGA

This is the companion repo for [Implementing Multi-Tenancy in Chroma: Part 2 - Authorization Model with OpenFGA](TBD)

`model-article-p4.fga` is the final authorization model that should be used. The others are just intermediate steps.

`test.model-article-p4.fga.yaml` contains the tests for the model.

## Requirements

- [Required] OpenFGA CLI - https://openfga.dev/docs/getting-started/install-sdk
- [Optional] VS code + VS Code extension for
  OpenFGA - https://marketplace.visualstudio.com/items?itemName=openfga.openfga-vscode

## Get Started

1. Clone this repo

```bash
git clone https://github.com/amikos-tech/chromadb-auth
```

2. Install OpenFGA CLI

3. Validate the model

```bash
fga model validate --file model-article-p4.fga
```

4. Test the model

```bash
fga model test --tests test.model-article-p4.fga.yaml
```
