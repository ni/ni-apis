# LabVIEW companion protos

This folder contains LabVIEW-only companions of canonical `.proto` files under
`ni/`. Use them only to generate LabVIEW gRPC clients with
[grpc-labview](https://github.com/ni/grpc-labview). Do not use them for servers
or for clients in other languages; use the canonical files instead.

The canonical files remain the source of truth. A companion changes only what
the grpc-labview generator or a LabVIEW client cannot handle, and keeps the
wire format compatible with the canonical contract.

Each companion has a `README.md` next to it that lists its differences from the
canonical files.

| Companion | Canonical | Details |
|---|---|---|
| `labview/ni/measurements/data/v2/` | `ni/measurements/data/v2/` | [MDS Data Store v2](ni/measurements/data/v2/README.md) |

## Layout and naming

A companion of `<path>/<name>.proto` is
`labview/<path>/<name>_labview.proto`. It keeps the canonical package, service,
message, and field names, because the gRPC method path
(`/<package>.<service>/<method>`) must match the server. The `_labview` suffix
stops a build from picking the wrong file by accident.

## Why this folder is outside `ni/`

Because a companion reuses the canonical package and message names, compiling
it together with its canonical file fails with duplicate definitions. The
`ni/` check compiles every file under `ni/` in one `protoc` run, so companions
live under `labview/` and are checked in a separate run.

## Allowed differences

A companion may differ from its canonical file only in these ways:

| Difference | Rule |
|---|---|
| A recursive well-known type (`google.protobuf.Struct`) | Replace it with `bytes` at the same field number and name. The bytes carry the binary-serialized message |
| A field LabVIEW cannot use | Remove it and reserve both its number and its name |
| A singular message field that a LabVIEW client must be able to omit | Make it `repeated` with the same name, number, and message type, outside any `oneof`. Zero or one element is wire-compatible with the singular field; list the field in the companion's `README.md` |
| Imports | Import companions instead of canonical files, and drop imports that are no longer used |
| Comments | Add notes for LabVIEW client authors |

Everything else must match the canonical files: package, services, RPCs and
their request and response types, messages, enums and enum values, and field
names, numbers, types, labels, and `oneof` membership, except as allowed above.

The LabVIEW generator and LabVIEW clients also require that, for every message
reachable from a companion service:

1. No message contains itself, directly or indirectly.
2. No field uses `google.protobuf.Struct`, `Value`, `ListValue`, or `Any`.
3. No field is a proto3 `optional` field.
4. `oneof` fields are nested no more than two messages deep.
5. No RPC is client- or server-streaming.

## Automated check

`.github/check_protos/_check_protos.py` compiles every companion with `protoc`
and compares it with its canonical file. It fails on any difference that is not
allowed above and on any LabVIEW constraint violation. The PR check runs it.
To run it locally:

```bash
cd .github/check_protos
poetry install
poetry run python _check_protos.py
```

## Keeping a companion in sync

Update the companion in the same change as its canonical file, and apply only
the allowed differences. In particular:

- Add every new canonical field to the companion with the same name, number,
  and type, or reserve it if LabVIEW cannot use it.
- Add new values to any enum at the end, and never renumber existing values.
  Regenerate the LabVIEW client so it knows the new values.
- Mirror comment-only changes where they help LabVIEW client authors.

## Generating a LabVIEW client

The grpc-labview generator may not resolve imports that span several include
paths, so generate from one bundle folder:

1. **Build the bundle.** Copy the companion and every file it imports into one
   folder, keeping their relative paths, so that the folder contains `ni/` and
   `google/` at its top level. The companion's `README.md` lists the files.
   Take the `google/protobuf/` files from a `protoc` installation or the
   `grpcio-tools` Python package. Use a short folder path, because the
   generated file paths are long.
2. **Map a short drive.** Map the folder that contains the bundle to a drive
   letter (for example with `subst`). Use that drive for every later step,
   including the LabVIEW project; mixing two paths for the same files makes
   LabVIEW load them twice.
3. **Create an empty LabVIEW project** on the same drive.
4. **Run the generator** (**Tools » gRPC Server-Client [2] - Code
   Generator**):

   | Field | Value |
   |---|---|
   | Proto file | The companion service file in the bundle |
   | Import paths | The bundle folder only |
   | Target project | The empty project |
   | Target name | `My Computer` |
   | Generate server or client | `gRPC Client` |

5. **Check the result.** The generated library has one VI per RPC, and a mass
   compile of the generated folder reports no `Bad VI`.

When connecting from the generated client, use a `host:port` address without a
URL scheme. An `http://` prefix makes the call wait instead of failing.

## Adding a companion

1. Create `labview/<path>/<name>_labview.proto` from the canonical file, using
   only the allowed differences.
2. Add a `README.md` next to it that lists its differences and the files the
   generator needs, and add it to the table at the top of this file.
3. Add a `.github/CODEOWNERS` entry with the same owners as the canonical file.
4. Run the automated check.
