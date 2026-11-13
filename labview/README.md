# LabVIEW companion protos

This folder contains LabVIEW-only companions of canonical `.proto` files under
`ni/`. Use them only to generate LabVIEW gRPC clients with
[grpc-labview](https://github.com/ni/grpc-labview). Do not use them for servers
or for clients in other languages; use the canonical files instead.

The canonical files remain the source of truth. A companion changes only the
constructs that the grpc-labview generator cannot handle, such as recursive
messages, and keeps the wire format compatible with the canonical contract.

## Why this folder is outside `ni/`

A companion keeps the canonical package, service, and message names, because
the gRPC method path (`/<package>.<service>/<method>`) must match the server.
Compiling a companion together with its canonical file therefore fails with
duplicate definitions. Keeping companions under `labview/` keeps them out of
the `ni/` compilation set. Companion file names end in `_labview` so that a
build cannot pick the wrong file by accident.

## MDS Data Store v2

| Companion | Canonical |
|---|---|
| `labview/ni/measurements/data/v2/data_store_labview.proto` | `ni/measurements/data/v2/data_store.proto` |
| `labview/ni/measurements/data/v2/data_store_service_labview.proto` | `ni/measurements/data/v2/data_store_service.proto` |

Package `ni.measurements.data.v2`, service `DataStoreService`, all RPCs, all
messages, all enums, and all other field names and numbers are identical to
the canonical files. Only these items differ:

| Canonical | Companion | Reason |
|---|---|---|
| `google.protobuf.Struct value = 1` in `JsonValue` | `bytes value = 1` | `Struct` is recursive |
| `google.protobuf.Struct extension = 18` in `Measurement` | `bytes extension = 18` | `Struct` is recursive |
| `google.protobuf.Struct extension = 16` in `TestResult` | `bytes extension = 16` | `Struct` is recursive |
| `google.protobuf.Struct extension = 14` in `Step` | `bytes extension = 14` | `Struct` is recursive |
| `repeated Step children = 26` in `Step` | `reserved 26; reserved "children";` | `Step` contains `Step` |
| `uut_instance = 26`, `operator = 27`, `test_station = 28`, `test_description = 29`, `uut = 30` in `TestResult` | `reserved 26 to 30;` and the five names | A LabVIEW cluster cannot leave these absent, and the service rejects an empty inline resource sent with its ID |
| `ni.measurements.metadata.v1.Test test = 27` in `Step` | `reserved 27; reserved "test";` | Same as above |
| `import "google/protobuf/struct.proto"` | removed | No longer used |
| Service file imports `data_store.proto` | Imports `data_store_labview.proto` | Points at the companion |

Notes for LabVIEW client code:

- A `bytes` field that replaces a `Struct` carries the binary-serialized
  `google.protobuf.Struct` message, not JSON text. Send zero-length bytes when
  there is no value.
- Create child steps individually with `parent_step_id`, and rebuild the step
  hierarchy from `parent_step_id` when reading.
- Link metadata with `uut_instance_id`, `operator_id`, `test_station_id`,
  `test_description_id`, `uut_id`, and `Step.test_id` (ID or alias). Do not
  request the removed inline resources in read masks; the service would send
  them, and the LabVIEW client would discard them as unknown fields.
- In update and read masks, use the canonical field names.

## Generating a LabVIEW client

The companion imports files from three locations. Give the generator these
include paths, or copy the files into one folder that keeps the same relative
paths:

| Include path | Provides |
|---|---|
| `labview/` | `ni/measurements/data/v2/data_store_labview.proto`, `ni/measurements/data/v2/data_store_service_labview.proto` |
| Repository root | `ni/datamonikers/v1/data_moniker.proto`, `ni/measurements/metadata/v1/metadata_store.proto`, `ni/protobuf/types/` (`array`, `attribute_value`, `precision_duration`, `precision_timestamp`, `scalar`, `vector`, `waveform`, `xydata`) |
| Protobuf well-known types (shipped with `protoc` and gRPC tools) | `google/protobuf/any.proto`, `google/protobuf/empty.proto`, `google/protobuf/field_mask.proto` |

Select `ni/measurements/data/v2/data_store_service_labview.proto` as the input
file. When connecting, use a `host:port` address without a URL scheme.

## Keeping a companion in sync

Update the companion in the same change as, or immediately after, any change to
its canonical file. Derive it by applying only the transformations listed above
to the current canonical file, and update the commit reference in the file
header.

A companion is in sync when all of these hold:

1. Package, services, RPCs, request and response types, messages, enums, enum
   values, field names, numbers, types, and labels match the canonical files,
   except for the documented differences.
2. No message refers to itself, directly or indirectly, in the import set.
3. The import set contains no `google.protobuf.Struct`, `Value`, or `ListValue`,
   and no `google.protobuf.Any` is reachable from the companion's services.
4. There are no proto3 `optional` fields.
5. `oneof` fields are nested no more than two messages deep.
6. The companion's services have no streaming RPCs.
7. The companion compiles with the include paths above.

When adding values to `Outcome` or `Status`, add them at the end and regenerate
the LabVIEW client.
