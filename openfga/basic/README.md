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

Follow instructions at https://openfga.dev/docs/getting-started/install-sdk

3. Validate the model

```bash
fga model validate --file model-article-p4.fga
```

4. Test the model

```bash
fga model test --tests test.model-article-p4.fga.yaml
```

## Authorization With Chroma

Create a store and add the model to it:

```bash
export FGA_API_URL=http://localhost:8082
fga store create --model openfga/basic/model-article-p4.fga --name chromadb-auth
```

You should see a response like this:

```json
{
  "store": {
    "created_at": "2024-04-09T18:37:26.367747Z",
    "id": "01HV3VB347NPY3NMX6VQ5N2E23",
    "name": "chromadb-auth",
    "updated_at": "2024-04-09T18:37:26.367747Z"
  },
  "model": {
    "authorization_model_id": "01HV3VB34JAXWF0F3C00DFBZV4"
  }
}

```

Export vars so that `fga` can work with the store:

```bash
export FGA_STORE_ID=01HV4HEXCEPZW0Z65023G4RSTP
export FGA_MODEL_ID=01HV4HEXCKNXTGQ6RCW5YEAHWG
```

Load the data types:

```bash
fga tuple write --file data/data/initial-data.json
```

You should see a list of successfully and unsuccessfully/failed written tuples.

Test the authorization model:

```bash
fga query check user:admin can_get_preflight server:localhost
```