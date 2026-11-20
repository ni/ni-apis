# MDS Data Store v2 LabVIEW companion

LabVIEW-only companion of the MDS Data Store v2 API. See the
[LabVIEW companion README](../../../../README.md) for the general rules.

| Companion | Canonical |
|---|---|
| `data_store_labview.proto` | `ni/measurements/data/v2/data_store.proto` |
| `data_store_service_labview.proto` | `ni/measurements/data/v2/data_store_service.proto` |

## Differences from the canonical files

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
| `uut_instance = 26`, `operator = 27`, `test_station = 28`, `test_description = 29`, `uut = 30` in `TestResult` | Reserved numbers and names | A LabVIEW cluster cannot leave these absent, and the service rejects an empty inline resource sent with its ID |
| `test = 27` in `Step` | Reserved number and name | Same as above |
| `software_items = 31`, `hardware_items = 32`, `test_adapters = 33` in `TestResult` | Reserved numbers and names | LabVIEW clients link metadata by ID only |
| `software_items = 26`, `hardware_items = 27`, `test_adapters = 28` in `Measurement` | Reserved numbers and names | Same as above |
| `repeated Step steps = 25` in `TestResult` | `reserved 25; reserved "steps";` | LabVIEW clients create each resource with its own call |
| `repeated Measurement measurements = 25` in `Step` | `reserved 25; reserved "measurements";` | Same as above |
| `MeasurementValue upper_limit = 8`, `MeasurementValue lower_limit = 9` in `Measurement` | `repeated MeasurementValue upper_limit = 8`, `repeated MeasurementValue lower_limit = 9` | A LabVIEW cluster cannot leave a limit absent, and the service rejects an empty limit. An empty array sends nothing |
| `import "google/protobuf/struct.proto"` and `import "ni/measurements/metadata/v1/metadata_store.proto"` | Removed | No longer used |
| Service file imports `data_store.proto` | Imports `data_store_labview.proto` | Points at the companion |

## Notes for LabVIEW client code

- A `bytes` field that replaces a `Struct` carries the binary-serialized
  `google.protobuf.Struct` message, not JSON text. Send zero-length bytes when
  there is no value.
- Link metadata by ID or alias with `uut_instance_id`, `operator_id`,
  `test_station_id`, `test_description_id`, `uut_id`, `Step.test_id`,
  `software_item_ids`, `hardware_item_ids`, and `test_adapter_ids`. Create new
  metadata through the metadata API first.
- Create each Step with `CreateStep` and each Measurement with
  `CreateMeasurement`, naming the parent with `test_result_id`,
  `parent_step_id`, or `step_id`. Rebuild the Step hierarchy from
  `parent_step_id` when reading.
- Send `Measurement.upper_limit` and `lower_limit` as an array of zero or one
  element. An empty array omits the limit; more than one element is merged
  into one value by the service. When reading, a limit is present when its
  array has one element.
- Do not request removed fields in read masks. The service would send them, and
  the LabVIEW client would discard them as unknown fields.
- In update and read masks, use the canonical field names.

## Files for the generator

Generate from `data_store_service_labview.proto`. The bundle folder needs these
files:

| Source | Files |
|---|---|
| `labview/` | `ni/measurements/data/v2/data_store_labview.proto`, `ni/measurements/data/v2/data_store_service_labview.proto` |
| `ni/` | `ni/datamonikers/v1/data_moniker.proto`, `ni/protobuf/types/` (`array`, `attribute_value`, `precision_duration`, `precision_timestamp`, `scalar`, `vector`, `waveform`, `xydata`) |
| Protobuf well-known types | `google/protobuf/any.proto`, `google/protobuf/empty.proto`, `google/protobuf/field_mask.proto` |

Generating the full client with grpc-labview 1.7.0.1 in LabVIEW 2026 takes
about an hour.
