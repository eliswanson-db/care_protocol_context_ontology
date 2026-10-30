"""Stage the Synthea JAR into a UC Volume (download once; pinned). No git-committed binary.

The ~200 MB JAR is not committed to git; it is staged into a Volume so runtime is offline/reproducible
(same policy as terminology: vendor the small stuff, stage the large binary). Pin SYNTHEA_JAR_URL to a
specific release tag after the first successful stage for full reproducibility.
"""
import argparse
import os
import urllib.request

# Pinned-by-default to the latest published release asset; replace with a tagged URL to pin a version.
DEFAULT_URL = "https://github.com/synthetichealth/synthea/releases/latest/download/synthea-with-dependencies.jar"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--volume_dir", default="/Volumes/eli_test_classic_catalog/care_protocol/synthea")
    p.add_argument("--jar_url", default=os.environ.get("SYNTHEA_JAR_URL", DEFAULT_URL))
    args = p.parse_args()

    os.makedirs(args.volume_dir, exist_ok=True)
    dest = os.path.join(args.volume_dir, "synthea-with-dependencies.jar")
    if os.path.exists(dest) and os.path.getsize(dest) > 50_000_000:
        print(f"already staged: {dest} ({os.path.getsize(dest):,} bytes)")
        return
    print(f"downloading {args.jar_url} -> {dest}")
    urllib.request.urlretrieve(args.jar_url, dest)
    print(f"staged {os.path.getsize(dest):,} bytes")


if __name__ == "__main__":
    main()
