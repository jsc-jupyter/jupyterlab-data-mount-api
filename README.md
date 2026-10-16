# JupyterLab DataMount REST API

[![Documentation](https://img.shields.io/badge/Documentation-passed-green)](https://jsc-jupyter.github.io/jupyterlab-data-mount/architecture/backend_api/)
[![Docker](https://img.shields.io/badge/DockerImage-passed-green)](https://hub.docker.com/r/jupyterjsc/jupyterlab-data-mount-api)
  
This is the backend implementation for the [JupyterLab DataMount Extension](https://github.com/jsc-jupyter/jupyterlab-data-mount).  
  
## API bind address

The API listens on `127.0.0.1:8090` by default, for use as a sidecar in the same Kubernetes Pod as JupyterLab. For a separate API deployment, set `GUNICORN_BIND` to its required address, for example `0.0.0.0:8090`. The API has no authentication, so restrict network access before binding to a non-loopback address.

![JupyterLab](https://jsc-jupyter.github.io/jupyterlab-data-mount/images/jupyterlab.png)
