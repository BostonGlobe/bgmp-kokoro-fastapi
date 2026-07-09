# Kokoro TTS API Runbook
This document contains an overview of the processes for building, deploying, and maintaining the internal Kokoro TTS API service. It is not a guide for users seeking to use the API for TTS, that can be found here: [Kokoro Integration Quickstart](integration/QUICKSTART.md). 

## How To Build It

In the GitHub repo, there is a [Dockerfile](../docker/cpu/Dockerfile.optimized) that will containerize the API. There is also a [Jenkins pipeline](../pipelines/image/Jenkinsfile) that runs on a Docker agent node, and will build the container image, tag it appropriately with the image name and version, and push it to the [GitHub Container Registry](https://github.com/BostonGlobe/bgmp-kokoro-fastapi/pkgs/container/bgmp-kokoro-tts). 

### Parameters
| Field | Description |
| --- | --- |
| `IMAGE_NAME` | Name of the image, default is bgmp-kokoro-tts, likely does not need to be modified for a standard run. |
| `IMAGE_VERSION` | Version of the image, see Versioning section below. |
| `DRY_RUN` | Boolean of whether or not to push the image to GHCR, leave checked to just run the tests and the image build step, uncheck to validate image tag, build image, and push to GHCR. |

### Credentials
The Jenkins pipeline requires the following credentials:
GitHub PAT with write:packages access to The Boston Globe organization.
bgmp-kokoro-fastapi in the dev2 Jenkins environment. Expires Sep. 24, 2026.
[Instructions to generate new PAT](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic)

### Versioning
The service follows semantic versioning with major.minor.patch conventions. The Jenkins pipeline checks the container registry to see if the image tag already exists before building and pushing to enforce immutable tagging, i.e. there can only be one v1.0.0.

## How To Deploy It
Deploying the service is currently managed by Ops, using the following [docker-compose.yaml](https://github.com/BostonGlobe/ops-docker/blob/main/bgmp-kokoro-tts/compose.yaml) file.

## How To Maintain It
### Upstream Repo Upgrades

[remsky/Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) is the upstream open-source repo we’ve forked our API repo from. In the event that an update is published, if that update contains a Kokoro model upgrade or security fixes, we may need to sync our fork. After syncing the fork and confirming there are no regressions, rerun the build job to republish the container and file a ticket with the Operations team to upgrade the deployed version.
#### Ticket template: TODO

