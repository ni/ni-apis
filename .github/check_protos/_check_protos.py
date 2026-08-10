#!/usr/bin/env python3
"""Generates gRPC Python stubs from proto files."""

import pathlib
import sys
import importlib.resources
import grpc_tools.protoc

PROTO_ROOT_PATH = pathlib.Path(__file__).parent.parent.parent
PROTO_PATH = PROTO_ROOT_PATH / "ni"
GRPC_DEVICE_PROTO_PATH = PROTO_ROOT_PATH / "ni" / "grpcdevice" / "v1"

PROTO_FILES = list(path for path in PROTO_PATH.rglob("*.proto") if not path.is_relative_to(GRPC_DEVICE_PROTO_PATH))
GRPC_DEVICE_PROTO_FILES = list(GRPC_DEVICE_PROTO_PATH.rglob("*.proto"))

def main():
    # Generate python files from .proto files with protoc.
    arguments = [
        "protoc",
        f"--proto_path={str(PROTO_ROOT_PATH)}",
        f"--proto_path={str(GRPC_DEVICE_PROTO_PATH)}",
        f"--proto_path={importlib.resources.files('grpc_tools').joinpath('_proto')}",
        f"--python_out={str(PROTO_ROOT_PATH)}",
        f"--grpc_python_out={str(PROTO_ROOT_PATH)}",
    ]

    arguments += [str(path.relative_to(PROTO_ROOT_PATH)).replace("\\", "/") for path in PROTO_FILES]
    arguments += [str(path.relative_to(GRPC_DEVICE_PROTO_PATH)).replace("\\", "/") for path in GRPC_DEVICE_PROTO_FILES]

    print("::group::Arguments for protoc")
    for argument in arguments:
        print(argument)
    print("::endgroup::")

    result = grpc_tools.protoc.main(arguments)
    if result != 0:
        sys.exit(result)

if __name__ == "__main__":
    main()