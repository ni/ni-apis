#!/usr/bin/env python3
"""Generates gRPC Python stubs from proto files."""

import pathlib
import sys
import grpc_tools.protoc
import pkg_resources

PROTO_ROOT_PATH = pathlib.Path(__file__).parent.parent.parent
PROTO_PATH = PROTO_ROOT_PATH / "ni"
PROTO_FILES = list(PROTO_PATH.rglob("*.proto"))

# Generate python files from .proto files with protoc.
arguments = [
    "protoc",
    f"--proto_path={str(PROTO_ROOT_PATH)}",
    f"--proto_path={pkg_resources.resource_filename('grpc_tools', '_proto')}",
    f"--python_out={str(PROTO_PATH)}",
    f"--grpc_python_out={str(PROTO_PATH)}",
]

arguments += [str(path.relative_to(PROTO_ROOT_PATH)).replace("\\", "/") for path in PROTO_FILES]

results = grpc_tools.protoc.main(arguments)
if results != 0:
    sys.exit(-1)