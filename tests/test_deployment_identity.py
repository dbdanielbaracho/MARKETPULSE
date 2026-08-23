from pathlib import Path


def test_container_defaults_public_origin_to_predibeacon_domain():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "MP_PUBLIC_BASE_URL=https://predibeacon.com" in dockerfile
    assert "MP_PUBLIC_BASE_URL=https://marketpulse-production" not in dockerfile
