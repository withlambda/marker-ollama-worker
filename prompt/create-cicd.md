# Create CI/CD Pipeline

## Goal
Create a GitHub Actions workflow to automate the build and push process for the Docker image of this project to the GitHub Container Registry (GHCR).

## Functionality
The workflow should:
1.  **Trigger**: Run on push events to the `main` branch and on tag pushes (e.g., `v*`).
2.  **Checkout**: Check out the repository code.
3.  **Setup Docker**: Set up Docker Buildx for multi-platform builds (if needed) and caching.
4.  **Login**: Log in to the GitHub Container Registry (GHCR) using the `GITHUB_TOKEN`.
5.  **Metadata**: Extract metadata (tags, labels) for the Docker image.
6.  **Build & Push**: Build the Docker image using the `Dockerfile` in the root directory and push it to GHCR.

## Configuration
-   **Registry**: `ghcr.io`
-   **Image Name**: The image should be named after the repository (e.g., `ghcr.io/${{ github.repository }}`).
-   **Tags**:
    -   `latest`: For the most recent build on the `main` branch.
    -   `sha-<commit_hash>`: For versioning and traceability on every commit.
    -   `v<version>`: When a git tag is pushed (e.g., `v1.0.0`).

## Implementation Details
-   **Permissions**: Explicitly set `packages: write` and `contents: read` permissions for the `GITHUB_TOKEN` in the workflow file.
-   **Actions**:
    -   `actions/checkout`
    -   `docker/setup-buildx-action` (for advanced build features and caching)
    -   `docker/login-action`
    -   `docker/metadata-action` (to handle tags and labels automatically)
    -   `docker/build-push-action`
-   **Caching**: Implement caching for Docker layers (using `gha` cache backend) to speed up subsequent builds.

## Output
Generate the following file:
1.  `.github/workflows/docker-publish.yml`: The complete, ready-to-use GitHub Actions workflow file.

## License

[GNU General Public License v3.0](../LICENSE)
