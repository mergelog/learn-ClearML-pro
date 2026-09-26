"""一時検証用: mp20260926プロジェクトへデータセットを1件だけ登録する。

経緯と使い方は x-mp20260926.md を参照。役目を終えたら本ファイルと
pyproject.toml の per-file-ignores のエントリごと削除してよい。
"""

from __future__ import annotations

import sys
from urllib.error import HTTPError, URLError

from clearml import Dataset, Task

from tools.semiconductor_seed.config import Settings
from tools.semiconductor_seed.generator import DATASET_VERSIONS, generate_dataset
from tools.semiconductor_seed.server_health import ensure_server_is_ready

PROJECT_NAME = "mp20260926"
DATASET_NAME = "semiconductor-quality-data"


def main() -> int:
    try:
        settings = Settings.from_environment()
        ensure_server_is_ready(settings.api_host)
        Task.set_credentials(
            api_host=settings.api_host,
            web_host=settings.web_host,
            files_host=settings.files_host,
            key=settings.access_key,
            secret=settings.secret_key,
        )

        definition = DATASET_VERSIONS[0]
        existing = _find_existing(definition.version)
        if existing is not None:
            print(f"Dataset already registered: {existing.id}")
            return 0

        dataset = generate_dataset(
            definition,
            settings.output_dir / "mp20260926",
            settings.random_seed,
        )
        created = Dataset.create(
            dataset_project=PROJECT_NAME,
            dataset_name=DATASET_NAME,
            dataset_version=definition.version,
            output_uri=settings.files_host,
            description=definition.description,
        )
        created.add_files(dataset.csv_path)
        created.upload(show_progress=False, verbose=False)
        created.finalize(verbose=False)
        print(
            f"Dataset ready: {definition.version} ({created.id}) "
            f"in project {PROJECT_NAME!r}"
        )
        return 0
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as error:
        print(f"mp20260926 dataset seed failed: {error}", file=sys.stderr)
        return 1


def _find_existing(version: str) -> Dataset | None:
    try:
        return Dataset.get(
            dataset_project=PROJECT_NAME,
            dataset_name=DATASET_NAME,
            dataset_version=version,
            only_completed=True,
        )
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
