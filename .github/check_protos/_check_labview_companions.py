"""Checks the LabVIEW companion .proto files under labview/ against their canonical files under ni/.

A companion ``labview/<path>/<name>_labview.proto`` mirrors ``<path>/<name>.proto``. The check compiles both
with protoc and fails when the companion drifts from the canonical contract or uses a construct that the
grpc-labview generator cannot handle. See labview/README.md for the rules.
"""

from __future__ import annotations

import importlib.resources
import pathlib
import tempfile

import grpc_tools.protoc
from google.protobuf import descriptor_pb2

FieldDescriptorProto = descriptor_pb2.FieldDescriptorProto

COMPANION_SUFFIX = "_labview.proto"
STRUCT_TYPE = ".google.protobuf.Struct"
RECURSIVE_WELL_KNOWN_TYPES = {STRUCT_TYPE, ".google.protobuf.Value", ".google.protobuf.ListValue"}
ANY_TYPE = ".google.protobuf.Any"
MAX_ONEOF_DEPTH = 2


def check_labview_companions(repo_root: pathlib.Path) -> list[str]:
    """Returns one message per problem found; an empty list means every companion passed."""
    labview_root = repo_root / "labview"
    pairs: list[tuple[str, str]] = []
    errors: list[str] = []
    for companion in sorted(labview_root.rglob(f"*{COMPANION_SUFFIX}")):
        companion_name = companion.relative_to(labview_root).as_posix()
        canonical_name = companion_name[: -len(COMPANION_SUFFIX)] + ".proto"
        if not (repo_root / canonical_name).is_file():
            errors.append(f"labview/{companion_name}: canonical file '{canonical_name}' does not exist.")
        else:
            pairs.append((companion_name, canonical_name))
    if errors or not pairs:
        return errors

    well_known_path = str(importlib.resources.files("grpc_tools").joinpath("_proto"))
    companion_set = _compile([labview_root, repo_root, well_known_path], [companion for companion, _ in pairs])
    canonical_set = _compile([repo_root, well_known_path], [canonical for _, canonical in pairs])
    if companion_set is None:
        return ["The LabVIEW companion .proto files do not compile; see the protoc errors above."]
    if canonical_set is None:
        return ["The canonical .proto files for the LabVIEW companions do not compile; see the protoc errors above."]

    companion_files = {file.name: file for file in companion_set.file}
    canonical_files = {file.name: file for file in canonical_set.file}
    for companion_name, canonical_name in pairs:
        errors += _compare_files(canonical_files[canonical_name], companion_files[companion_name])
    errors += _check_labview_constraints(companion_set, [companion_files[name] for name, _ in pairs])
    return errors


def _compile(include_paths: list, files: list[str]) -> descriptor_pb2.FileDescriptorSet | None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output = pathlib.Path(temp_dir) / "descriptors.pb"
        arguments = ["protoc", *[f"--proto_path={path}" for path in include_paths]]
        arguments += ["--include_imports", f"--descriptor_set_out={output}", *files]
        if grpc_tools.protoc.main(arguments) != 0:
            return None
        descriptor_set = descriptor_pb2.FileDescriptorSet()
        descriptor_set.ParseFromString(output.read_bytes())
        return descriptor_set


def _walk_messages(prefix: str, messages):
    for message in messages:
        full_name = f"{prefix}.{message.name}"
        yield full_name, message
        yield from _walk_messages(full_name, message.nested_type)


def _enums(file: descriptor_pb2.FileDescriptorProto) -> dict[str, list[tuple[str, int]]]:
    prefix = f".{file.package}"
    enums = {f"{prefix}.{enum.name}": [(value.name, value.number) for value in enum.value] for enum in file.enum_type}
    for full_name, message in _walk_messages(prefix, file.message_type):
        for enum in message.enum_type:
            enums[f"{full_name}.{enum.name}"] = [(value.name, value.number) for value in enum.value]
    return enums


def _methods(file: descriptor_pb2.FileDescriptorProto) -> dict[str, tuple]:
    return {
        f"{service.name}.{method.name}": (
            method.input_type,
            method.output_type,
            method.client_streaming,
            method.server_streaming,
        )
        for service in file.service
        for method in service.method
    }


def _oneof_name(message: descriptor_pb2.DescriptorProto, field: FieldDescriptorProto) -> str | None:
    return message.oneof_decl[field.oneof_index].name if field.HasField("oneof_index") else None


def _compare_files(canonical: descriptor_pb2.FileDescriptorProto, companion: descriptor_pb2.FileDescriptorProto) -> list[str]:
    where = f"labview/{companion.name}"
    errors: list[str] = []
    if canonical.package != companion.package:
        errors.append(f"{where}: package '{companion.package}' must match canonical package '{canonical.package}'.")

    canonical_enums, companion_enums = _enums(canonical), _enums(companion)
    for name in sorted(canonical_enums.keys() | companion_enums.keys()):
        if canonical_enums.get(name) != companion_enums.get(name):
            errors.append(f"{where}: enum {name} values must match the canonical enum.")

    canonical_methods, companion_methods = _methods(canonical), _methods(companion)
    for name in sorted(canonical_methods.keys() | companion_methods.keys()):
        if canonical_methods.get(name) != companion_methods.get(name):
            errors.append(f"{where}: RPC {name} must match the canonical RPC (missing, extra, or different types).")

    canonical_messages = dict(_walk_messages(f".{canonical.package}", canonical.message_type))
    companion_messages = dict(_walk_messages(f".{companion.package}", companion.message_type))
    for name in sorted(canonical_messages.keys() - companion_messages.keys()):
        errors.append(f"{where}: message {name} is missing from the companion.")
    for name in sorted(companion_messages.keys() - canonical_messages.keys()):
        errors.append(f"{where}: message {name} is not in the canonical file.")
    for name in sorted(canonical_messages.keys() & companion_messages.keys()):
        errors += [f"{where}: {problem}" for problem in _compare_messages(name, canonical_messages[name], companion_messages[name])]
    return errors


def _compare_messages(name: str, canonical: descriptor_pb2.DescriptorProto, companion: descriptor_pb2.DescriptorProto) -> list[str]:
    errors: list[str] = []
    reserved_numbers = {number for reserved in companion.reserved_range for number in range(reserved.start, reserved.end)}
    reserved_names = set(companion.reserved_name)
    canonical_fields = {field.number: field for field in canonical.field}
    companion_fields = {field.number: field for field in companion.field}

    for number, canonical_field in sorted(canonical_fields.items()):
        field_name = f"{name}.{canonical_field.name} = {number}"
        companion_field = companion_fields.get(number)
        if companion_field is None:
            if number not in reserved_numbers or canonical_field.name not in reserved_names:
                errors.append(f"field {field_name} is missing; add it, or reserve both its number and its name.")
            continue

        is_struct_as_bytes = (
            canonical_field.type == FieldDescriptorProto.TYPE_MESSAGE
            and canonical_field.type_name == STRUCT_TYPE
            and companion_field.type == FieldDescriptorProto.TYPE_BYTES
        )
        
        is_message_as_repeated = (
            canonical_field.type == FieldDescriptorProto.TYPE_MESSAGE
            and canonical_field.label == FieldDescriptorProto.LABEL_OPTIONAL
            and companion_field.label == FieldDescriptorProto.LABEL_REPEATED
            and not canonical_field.HasField("oneof_index")
        )
        if (
            companion_field.name != canonical_field.name
            or (companion_field.label != canonical_field.label and not is_message_as_repeated)
            or _oneof_name(canonical, canonical_field) != _oneof_name(companion, companion_field)
            or companion_field.proto3_optional != canonical_field.proto3_optional
            or not (
                is_struct_as_bytes
                or (companion_field.type, companion_field.type_name) == (canonical_field.type, canonical_field.type_name)
            )
        ):
            errors.append(f"field {field_name} must match the canonical field (name, type, label, and oneof).")

    for number, companion_field in sorted(companion_fields.items()):
        if number not in canonical_fields:
            errors.append(f"field {name}.{companion_field.name} = {number} is not in the canonical message.")

    canonical_oneofs = {oneof.name for oneof in canonical.oneof_decl}
    companion_oneofs = {oneof.name for oneof in companion.oneof_decl}
    if canonical_oneofs != companion_oneofs:
        errors.append(f"message {name} oneofs {sorted(companion_oneofs)} must match canonical oneofs {sorted(canonical_oneofs)}.")
    return errors


def _check_labview_constraints(
    descriptor_set: descriptor_pb2.FileDescriptorSet, companions: list[descriptor_pb2.FileDescriptorProto]
) -> list[str]:
    messages = {}
    for file in descriptor_set.file:
        for full_name, message in _walk_messages(f".{file.package}" if file.package else "", file.message_type):
            messages[full_name] = message

    errors: list[str] = []
    roots: list[str] = []
    for companion in companions:
        for service in companion.service:
            for method in service.method:
                if method.client_streaming or method.server_streaming:
                    errors.append(f"labview/{companion.name}: streaming RPC {service.name}.{method.name} is not supported.")
                roots += [method.input_type, method.output_type]

    reachable: set[str] = set()
    pending = list(dict.fromkeys(roots))
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        for field in messages[name].field:
            # Banned types are reported where they are used; their own internals are not walked.
            if field.type_name in messages and field.type_name not in RECURSIVE_WELL_KNOWN_TYPES | {ANY_TYPE}:
                pending.append(field.type_name)

    for name in sorted(reachable):
        for field in messages[name].field:
            if field.type_name in RECURSIVE_WELL_KNOWN_TYPES:
                errors.append(f"{name}.{field.name} uses recursive type {field.type_name}; use bytes instead.")
            elif field.type_name == ANY_TYPE:
                errors.append(f"{name}.{field.name} uses {ANY_TYPE}, which grpc-labview cannot generate.")
            if field.proto3_optional:
                errors.append(f"{name}.{field.name} is a proto3 optional field, which LabVIEW cannot represent.")

    children = {
        name: [
            field.type_name
            for field in messages[name].field
            if field.type_name in messages and field.type_name not in RECURSIVE_WELL_KNOWN_TYPES | {ANY_TYPE}
        ]
        for name in reachable
    }
    visiting: list[str] = []
    finished: set[str] = set()

    def find_cycle(name: str) -> list[str] | None:
        if name in finished:
            return None
        if name in visiting:
            return visiting[visiting.index(name) :] + [name]
        visiting.append(name)
        for child in children[name]:
            cycle = find_cycle(child)
            if cycle:
                return cycle
        visiting.pop()
        finished.add(name)
        return None

    for name in sorted(reachable):
        cycle = find_cycle(name)
        if cycle:
            errors.append(f"recursive message {' -> '.join(cycle)}; grpc-labview cannot generate it.")
            return errors

    depths: dict[str, int] = {}

    def oneof_depth(name: str) -> int:
        if name not in depths:
            message = messages[name]
            arms = [
                field.type_name
                for field in message.field
                if field.HasField("oneof_index") and field.type_name in children
            ]
            depths[name] = 1 + max((oneof_depth(arm) for arm in arms), default=0) if message.oneof_decl else 0
        return depths[name]

    for name in sorted(reachable):
        depth = oneof_depth(name)
        if depth > MAX_ONEOF_DEPTH:
            errors.append(f"message {name} nests oneofs {depth} levels deep; the limit is {MAX_ONEOF_DEPTH}.")
    return errors
