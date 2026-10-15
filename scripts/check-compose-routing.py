"""Render real Compose configurations and verify distinct Traefik names (no daemon needed)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check():
    with tempfile.TemporaryDirectory(prefix="iorp-compose-") as directory:
        env_file = Path(directory) / "empty.env"
        env_file.write_text("", encoding="utf-8")
        for stage, subnet in (("staging", "172.28.10.0/24"), ("production", "172.28.11.0/24")):
            project = f"iorp-{stage}"
            domain = f"{project}.example.invalid"
            env = {
                **os.environ,
                "IORP_PROJECT": project,
                "IORP_IMAGE_TAG": "routing-check",
                "IORP_REGISTRY": "iorp",
                "IORP_DOMAIN": domain,
                "IORP_APP_SUBNET": subnet,
                "IORP_BACKEND_ENV_FILE": env_file.as_posix(),
                "IORP_POSTGRES_ENV_FILE": env_file.as_posix(),
                "TRAEFIK_NETWORK": "proxy",
                "TRAEFIK_ENTRYPOINT": "websecure",
                "TRAEFIK_CERTRESOLVER": "le",
            }
            result = subprocess.run(
                ["docker", "compose", "--env-file", str(env_file), "-f",
                 str(ROOT / "deploy/compose.yaml"), "config", "--format", "json"],
                env=env, check=True, capture_output=True, text=True,
            )
            config = json.loads(result.stdout)
            labels = config["services"]["frontend"]["labels"]
            if config["name"] != project:
                raise AssertionError(config["name"])
            for category in ("routers", "services"):
                prefix = f"traefik.http.{category}."
                names = {key[len(prefix):].split(".")[0] for key in labels if key.startswith(prefix)}
                if names != {project}:
                    raise AssertionError(f"{stage}: unexpected {category}: {names}")
            expected = {
                f"traefik.http.routers.{project}.rule": f"Host(`{domain}`)",
                f"traefik.http.routers.{project}.service": project,
                f"traefik.http.services.{project}.loadbalancer.server.port": "3000",
            }
            for key, value in expected.items():
                if labels.get(key) != value:
                    raise AssertionError(f"{key}: {labels.get(key)!r} != {value!r}")
            if any("${" in item for pair in labels.items() for item in pair):
                raise AssertionError(f"{stage}: unresolved label interpolation")
            print(f"PASS: {project} router and service, domain {domain}")


if __name__ == "__main__":
    check()
