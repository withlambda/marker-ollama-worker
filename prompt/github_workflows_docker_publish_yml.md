# Context
This GitHub Actions workflow, located at `.github/workflows/docker-publish.yml`, automates the project's container build and publication to the GitHub Container Registry (GHCR). It is triggered by new release tags (`v*.*.*`) or manually.

# Interface

## Triggers
- `workflow_dispatch`, `workflow_call`.
- `push` with tags: `v*.*.*`.

## Environment Variables
- `REGISTRY`: `ghcr.io`.
- `IMAGE_NAME`: Current repository identifier (`<account>/<repo>`).

# Logic
1.  **Preparation**:
    - Checkout the repository.
    - Frees up disk space (approx. 6GB) by removing unused system tools.
    - Reads the `VERSION` file to use it for Docker tags.
2.  **Infrastructure**:
    - Sets up `Docker Buildx` for multi-platform support and caching.
    - Logs into the GHCR using the `GITHUB_TOKEN`.
3.  **Metadata**:
    - Generates Docker tags (semver, branch, sha, and current version) and labels using the `docker/metadata-action`.
4.  **Build and Push**:
    - Builds the image using the root `Dockerfile`.
    - Pushes the image to `ghcr.io` (skipped for pull requests).
    - Uses GitHub Actions' built-in cache (`type=gha`) to speed up subsequent builds.

# Goal
The prompt file provides the full CI specification for Docker image management, including tagging strategies, registry integration, and runner optimizations.
