"""Stage client files."""

from argparse import ArgumentParser
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

class _ArtifactLocations:
    repo_root: Path

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    @property
    def proto_files(self) -> Path:
        return self.repo_root


def stage_ci_files(output_path: Path):
    """Stage the client files into the given output path."""
    repo_root = Path(__file__).parent.parent.parent
    artifact_locations = _ArtifactLocations(repo_root)

    proto_path = output_path / "proto"
    proto_path.mkdir(parents=True)

    for file in artifact_locations.proto_files.glob("*.proto"):
        copy2(file, proto_path)


if __name__ == "__main__":
    parser = ArgumentParser(description="Stage ni-api files.")
    parser.add_argument(
        "--output",
        "-o",
        help="The path to the top-level directory to stage the client files. Must be empty or non-existent.",
    )

    args = parser.parse_args()

    if args.output:
        stage_ci_files(Path(args.output))
    else:
        print(
            """
***No --output directory specified.***
Performing Dry Run.
        """
        )
        with TemporaryDirectory() as tempdir:
            tempdirpath = Path(tempdir)
            stage_ci_files(tempdirpath)
            created_files = (f for f in tempdirpath.glob("**/*") if not f.is_dir())
            for out_file in created_files:
                print(out_file.relative_to(tempdirpath))