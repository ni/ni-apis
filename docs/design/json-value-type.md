# Design Document: JSON Value Type Support for Measurement Data

**Status:** Draft

**Author:** Nick Beer

**Created:** 2026-02-13

**Last Updated:** 2026-02-13

## Overview

This document describes the design of JSON value type support for the NI Measurements Data infrastructure. This enhancement adds support for arbitrary, schema-validated JSON data as a first-class measurement value type.

## References

- [Protocol Buffers: google.protobuf.Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)
- [JSON Schema Specification](https://json-schema.org/)
- [NI Measurements Metadata Service API](ni/measurements/metadata/v1/metadata_store_service.proto)
- [NI Measurements Data Store Service API](ni/measurements/data/v1/data_store_service.proto)

## Background

### Problem Statement

The current measurement data infrastructure supports a fixed set of strongly-typed value types (scalar, vector, waveform, XY data, spectrum, etc.). Users across multiple domains — including NI TestStand sequences, Python-based test automation, and other MDS clients — often work with complex, hierarchical data structures that don't map cleanly to these predefined types.

For example, TestStand customers commonly create arbitrary data structures in their code modules, and Python API users frequently work with nested dictionaries and domain-specific objects. When these users attempt to publish their data to Measurement Data Services (MDS), they face significant challenges because their existing data structures can't be represented directly.

This forces users to make compromises:
1. Flatten their data structures, losing the semantic relationships between values
2. Manually serialize to strings, losing structure and queryability
3. Simply not publish certain measurements to MDS

By adding a JSON value type, users can publish their existing structured data with minimal transformation while preserving its semantic meaning, and MDS can validate the data against a known schema.

Note: The existing `extension` fields on `TestResult` and `Step` are designed for extending metadata associated with those metadata objects, not for measurement data itself.

### Goals

1. Enable publishing arbitrary structured data as measurement values, supporting existing workflows in TestStand, Python, and other MDS clients
2. Maintain type safety through schema validation for MDS
3. Provide ergonomic APIs across all supported languages
4. Preserve backward compatibility with existing clients and servers
5. Follow existing architectural patterns in the codebase

### Non-Goals

1. Support for JSON values in condition publishing (deferred to future work)
2. Support for JSON values in batch operations (deferred to future work)
3. Automatic schema inference or generation
4. Support for non-JSON structured data formats (Protocol Buffers, XML, etc.)

## Design

### High-Level Architecture

The design introduces a new protobuf type `JsonValue` that wraps `google.protobuf.Struct` with a `schema_id` field. This hybrid approach combines:

- **Structured data ergonomics** from `google.protobuf.Struct`
- **Schema binding** following existing metadata extension patterns
- **Type system consistency** with other wrapper types like `Scalar` and `Vector`

```
┌─────────────────────────────────────┐
│  PublishMeasurementRequest          │
│  ┌────────────────────────────────┐ │
│  │ oneof value {                  │ │
│  │   Scalar scalar                │ │
│  │   Vector vector                │ │
│  │   ...                          │ │
│  │   JsonValue json_value ◄────┐  │ │
│  │ }                           │  │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
                                 │
                    ┌────────────┘
                    │
         ┌──────────▼──────────────────────┐
         │  ni.protobuf.types.JsonValue    │
         │  ┌────────────────────────────┐ │
         │  │ Struct value               │ │
         │  │ string schema_id ──────────┼─┼──┐
         │  │ map attributes             │ │  │
         │  └────────────────────────────┘ │  │
         └─────────────────────────────────┘  │
                                              │
         ┌────────────────────────────────────┘
         │  references
         │
         ▼
┌─────────────────────────────────────────┐
│  DataStoreService                       │
│  ┌────────────────────────────────────┐ │
│  │ RegisterValueSchema()              │ │
│  │   request:  string schema          │ │
│  │   response: string schema_id       │ │
│  ├────────────────────────────────────┤ │
│  │ ListValueSchemas()                 │ │
│  │   response: repeated ValueSchema   │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Detailed Design

#### 1. New Type: `ni.protobuf.types.JsonValue`

**Location:** `ni/protobuf/types/json_value.proto`

```protobuf
syntax = "proto3";

package ni.protobuf.types;

import "google/protobuf/struct.proto";
import "ni/protobuf/types/attribute_value.proto";

option csharp_namespace = "NationalInstruments.Protobuf.Types";
option go_package = "types";
option java_multiple_files = true;
option java_outer_classname = "JsonValueProto";
option java_package = "com.ni.protobuf.types";
option objc_class_prefix = "NIPT";
option php_namespace = "NI\\PROTOBUF\\TYPES";
option ruby_package = "NI::Protobuf::Types";

// A JSON value with an associated schema identifier.
//
// The JSON content is represented as a google.protobuf.Struct, which provides
// structured data handling across all language bindings. The schema_id references
// a schema that can be used for validation.
//
// Example usage:
//   JsonValue psu_result = {
//     value: {
//       "output_voltage": 12.03,
//       "output_current": 2.51,
//       "load_regulation": { ... }
//     },
//     schema_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
//   };
message JsonValue {
  // Required. The JSON content as a structured value.
  google.protobuf.Struct value = 1;

  // Required. The identifier of the schema associated with this JSON content.
  // For Measurement Data Services (MDS), this schema_id must reference a registered
  // schema and will be validated server-side. Other consumers of this type may have
  // different requirements for schema validation.
  string schema_id = 2;

  // The names and values of all JSON value attributes.
  //
  // A JSON value attribute is metadata attached to a JSON value.
  // It is represented in this message as a map associating the name of
  // the attribute with the value described by AttributeValue.
  map<string, AttributeValue> attributes = 3;
}
```

**Design Rationale:**

- **`google.protobuf.Struct` for value**: Provides native, idiomatic data structure handling in all languages (dict in Python, Map in Java, Dictionary in C#, etc.). Avoids manual JSON string serialization/deserialization.

- **Bundled `schema_id`**: Keeps schema and data together as an atomic unit, following existing metadata extension patterns (similar to how `extension` and `schema_id` are paired in metadata objects like `TestResult` and `Step`). Prevents accidental schema/data mismatches.

- **Schema validation**: For MDS, the `schema_id` field is required and validated server-side. Other consumers of the `JsonValue` type in ni-apis may have different validation requirements or may use the type without strict schema enforcement.

- **`attributes` field**: Consistent with all other top-level measurement value types (`Scalar`, `Vector`, `DoubleXYData`, waveform types, etc.), which all carry a `map<string, ...> attributes` field for attaching metadata to the value.

#### 2. Integration with Measurement Data APIs

##### PublishMeasurementRequest

**File:** `ni/measurements/data/v1/data_store_service.proto`

Add `json_value` to the value `oneof`:

```protobuf
import "ni/protobuf/types/json_value.proto";

message PublishMeasurementRequest {
  string name = 1;

  oneof value {
    ni.protobuf.types.Scalar scalar = 2;
    ni.protobuf.types.Vector vector = 3;
    ni.protobuf.types.DoubleAnalogWaveform double_analog_waveform = 4;
    ni.protobuf.types.DoubleXYData x_y_data = 5;
    ni.protobuf.types.I16AnalogWaveform i16_analog_waveform = 6;
    ni.protobuf.types.DoubleComplexWaveform double_complex_waveform = 7;
    ni.protobuf.types.I16ComplexWaveform i16_complex_waveform = 8;
    ni.protobuf.types.DoubleSpectrum double_spectrum = 9;
    ni.protobuf.types.DigitalWaveform digital_waveform = 10;
    ni.protobuf.types.JsonValue json_value = 19;  // NEW
  }

  string notes = 11;
  ni.protobuf.types.PrecisionTimestamp timestamp = 12;
  Outcome outcome = 13;
  ErrorInformation error_information = 14;
  string step_id = 15;
  repeated string hardware_item_ids = 16;
  repeated string test_adapter_ids = 17;
  repeated string software_item_ids = 18;
}
```

##### ReadMeasurementValueResponse

```protobuf
message ReadMeasurementValueResponse {
  oneof value {
    ni.protobuf.types.Vector vector = 1;
    ni.protobuf.types.DoubleAnalogWaveform double_analog_waveform = 2;
    ni.protobuf.types.DoubleXYData x_y_data = 3;
    ni.protobuf.types.I16AnalogWaveform i16_analog_waveform = 4;
    ni.protobuf.types.DoubleComplexWaveform double_complex_waveform = 5;
    ni.protobuf.types.I16ComplexWaveform i16_complex_waveform = 6;
    ni.protobuf.types.DoubleSpectrum double_spectrum = 7;
    ni.protobuf.types.DigitalWaveform digital_waveform = 8;
    ni.protobuf.types.JsonValue json_value = 9;  // NEW
  }
}
```

#### 3. Validation Strategy

**Server-side validation** occurs when `PublishMeasurement()` is called:

1. **Schema existence check**: Verify `JsonValue.schema_id` references a registered schema
2. **Schema validation**: Validate `JsonValue.value` conforms to the schema
3. **Reject on failure**: Return error with details if validation fails

**Validation timing:** Synchronous during the publish RPC call. Failed validation results in an error response; the measurement is not stored.

**Schema accessibility:** Schemas are stored server-side and may not be accessible to clients after registration. Clients are responsible for tracking which schema IDs correspond to which schemas.

**Note:** Schema registration is handled by `RegisterValueSchema` on `DataStoreService` (see Section 4).

#### 4. Schema Registration

Schema registration for `JsonValue` measurements lives on `DataStoreService`, keeping it in the data domain rather than the metadata domain. This is distinct from the existing `RegisterSchema` / `ListSchemas` RPCs on `MetadataStoreService`, which serve metadata extension schemas.

**New RPCs on `DataStoreService`:**

```protobuf
service DataStoreService {
  // ... existing RPCs ...

  // Registers a value schema for use with JsonValue measurements.
  // The schema must be a well-formed JSON Schema. Once registered, a schema
  // cannot be modified or removed.
  rpc RegisterValueSchema(RegisterValueSchemaRequest) returns (RegisterValueSchemaResponse);

  // Lists value schemas that have been previously registered.
  rpc ListValueSchemas(ListValueSchemasRequest) returns (ListValueSchemasResponse);
}
```

**Request/Response messages** (in `data_store_service.proto`):

```protobuf
message RegisterValueSchemaRequest {
  // Required. The JSON Schema content as a string.
  // Must be a well-formed JSON Schema (http://json-schema.org/) and must
  // include an "$id" field, which serves as the schema's unique identifier.
  // Validation is performed server-side, and an error is returned
  // if the schema is not valid or is missing the "$id" field.
  string schema = 1;
}

message RegisterValueSchemaResponse {
  // The identifier of the registered schema, matching the "$id" field
  // in the schema document.
  string schema_id = 1;
}

message ListValueSchemasRequest {
}

message ListValueSchemasResponse {
  repeated ValueSchema schemas = 1;
}
```

**Domain model message** (in `data_store.proto`):

```protobuf
// A value schema registered for use with JsonValue measurements.
message ValueSchema {
  // The schema identifier, matching the "$id" field in the schema document.
  string id = 1;
  // The JSON Schema content.
  string schema = 2;
}
```

**Design decisions:**

- **Immutable schemas**: Once registered, a schema cannot be modified or removed. This ensures that existing measurements always reference a valid, unchanged schema.
- **JSON Schema only**: Unlike the metadata service's `RegisterSchema` (which accepts JSON or TOML), `RegisterValueSchema` only accepts JSON Schema. Since the data being validated is JSON (Struct), restricting the schema format simplifies validation and avoids ambiguity.
- **Schema-defined IDs**: The `schema_id` returned by `RegisterValueSchema` is not server-generated — it is extracted from the `$id` field in the JSON Schema document itself. This field is required. The `$id` is a standard JSON Schema keyword that uniquely identifies the schema, and using it as the registration identifier ensures clients have a predictable, stable ID they control. Clients use this ID when constructing `JsonValue` messages.
- **String representation**: The schema is passed as a raw JSON string rather than a `google.protobuf.Struct`. JSON Schema documents contain features (`$ref`, `$schema`, `additionalProperties`, integer vs. number distinction) that don't round-trip cleanly through Struct. Schemas are pre-authored artifacts, not programmatically constructed — string preserves fidelity.

### API Examples

#### Python Example

```python
from google.protobuf import struct_pb2
from ni.measurements.data.v1 import data_store_service_pb2
from ni.protobuf.types import json_value_pb2

# Step 1: Register schema and obtain schema_id
schema_response = data_store_stub.RegisterValueSchema(
    RegisterValueSchemaRequest(schema=json.dumps(my_json_schema))
)
schema_id = schema_response.schema_id

# Step 2: Prepare measurement data
psu_data = {
    "output_voltage": 12.03,
    "output_current": 2.51,
    "load_regulation": {
        "no_load_voltage": 12.10,
        "full_load_voltage": 11.95,
        "regulation_percent": 1.24
    },
    "ripple_analysis": {
        "peak_to_peak_mv": 15.3,
        "rms_mv": 4.2,
        "frequency_hz": 120.0,
        "harmonics": [
            {"harmonic_number": 2, "amplitude_mv": 3.1, "frequency_hz": 240.0},
            {"harmonic_number": 3, "amplitude_mv": 1.5, "frequency_hz": 360.0}
        ]
    }
}

# Step 3: Convert to JsonValue
struct_value = struct_pb2.Struct()
struct_value.update(psu_data)

json_value = json_value_pb2.JsonValue(
    value=struct_value,
    schema_id=schema_id
)

# Step 4: Publish measurement
request = data_store_service_pb2.PublishMeasurementRequest(
    name="PowerSupplyCharacterization",
    json_value=json_value,
    timestamp=current_timestamp,
    step_id=step_id
)

response = data_store_stub.PublishMeasurement(request)
measurement_id = response.measurement_id

# Step 5: Read back measurement
read_response = data_store_stub.ReadMeasurementValue(
    ReadMeasurementValueRequest(measurement_id=measurement_id)
)

# Extract data
data_dict = dict(read_response.json_value.value)
schema_id = read_response.json_value.schema_id
```



## Compatibility Considerations

### Backward Compatibility

This change is **backward compatible**:

- **Old clients + New server**: Old clients can continue to publish existing value types. They cannot publish `json_value` until upgraded.
- **New clients + Old server**: New clients attempting to publish `json_value` will receive an error from old servers (unrecognized field in `oneof`). Clients should handle this gracefully.
- **Old clients reading new data**: If an old client reads a measurement that was published with `json_value`, it will see the `value` field as unset (proto3 `oneof` behavior). Applications should handle unknown value types.

### Forward Compatibility

The design is forward compatible:
- The `JsonValue` wrapper can be extended with additional fields without breaking changes (e.g., versioning, compression)

### Migration Strategy

**No migration required** for existing users. This is a purely additive change.

For users who want to adopt JSON values:
1. Register schemas via `DataStoreService.RegisterValueSchema`
2. Update client code to construct `JsonValue` messages
3. Test with development servers before production rollout

## Performance Considerations

### Wire Format Size

`google.protobuf.Struct` has modest overhead compared to raw JSON strings:
- Each field in the struct adds a small amount of framing (field numbers, wire types)
- For typical measurement payloads (10-100 fields), overhead is ~10-20% vs. raw JSON
- This overhead is acceptable given the ergonomic and type-safety benefits

### Serialization and Validation

When using `JsonValue`, there are several serialization steps in a typical workflow:

1. **Client-side**: Application data → `google.protobuf.Struct` (language-native conversion)
2. **Wire transport**: Struct serialized to protobuf binary format
3. **Server-side validation**: Struct → JSON string representation → schema validation
4. **Storage**: Implementation-dependent (may store as JSON, binary, etc.)

The Struct → JSON conversion on the server for schema validation adds minimal overhead (typically < 1ms for small-to-medium documents).

## Alternatives Considered

### Alternative 1: Plain String JSON

**Approach:** Add `string json_string` to the `oneof` with a parallel `string json_schema_id` field.

**Pros:**
- Simplest implementation
- Smallest wire format
- Consistent with `CreateFromJsonDocumentRequest`

**Cons:**
- Manual JSON serialization/deserialization in every language
- No type safety or structure information
- Poor developer experience
- Requires manual parsing for debugging/tooling

**Verdict:** Rejected due to poor ergonomics and lack of type safety.

### Alternative 2: google.protobuf.Struct with Parallel Schema Field

**Approach:** Add `google.protobuf.Struct json_value` to the `oneof` with a parallel `string json_schema_id` field at the message level.

**Pros:**
- Good ergonomics from Struct
- Standard protobuf type
- No custom wrapper needed

**Cons:**
- Schema and data not bundled together (can be mismatched)
- Breaks pattern established by `extension` + `schema_id` in existing metadata objects
- Schema field must be conditionally validated based on which `oneof` value is set
- Less clear API contract

**Verdict:** Rejected in favor of atomic bundling of schema + data.

### Alternative 3: google.protobuf.Any

**Approach:** Use `google.protobuf.Any` to embed arbitrary protobuf messages.

**Pros:**
- Native protobuf mechanism for polymorphic types
- Type URL provides some schema information

**Cons:**
- Requires all data to be defined as protobuf messages (defeats purpose of JSON support)
- No validation against user-defined schemas
- More complex to work with than Struct
- Not suitable for arbitrary JSON data

**Verdict:** Rejected as it doesn't solve the JSON use case.

## Open Questions

1. **Schema versioning**: Should we support versioned schemas? If a schema evolves, should old measurements reference the old schema version?
   - **Resolution:** Deferred to future work. Users can manually version schemas via naming conventions in schema content.

2. **Batch operations**: Should `PublishMeasurementBatch` support JSON values?
   - **Resolution:** Not in initial implementation. Deferred to future work based on user demand.

3. **Size limits**: What are appropriate size limits for JSON payloads?
   - **Resolution:** Use existing message size limits (server configuration). No special limits for JSON values.

4. **Schema format**: Should we support formats other than JSON Schema (e.g., TOML)?
   - **Resolution:** No. `RegisterValueSchema` accepts only JSON Schema, since the data being validated is JSON/Struct.

## Appendix: Schema Example

This example demonstrates how a power supply characterization test produces multiple related readings that form a cohesive measurement result — the kind of hierarchical data that users across TestStand, Python, and other MDS clients commonly need to publish.

### Power Supply Characterization Result

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://ni.com/schemas/power-supply-characterization/v1",
  "title": "Power Supply Characterization",
  "description": "Comprehensive power supply test results including output characteristics, ripple analysis, and transient response",
  "type": "object",
  "properties": {
    "output_voltage": {
      "type": "number",
      "description": "Measured DC output voltage in volts"
    },
    "output_current": {
      "type": "number",
      "description": "Measured DC output current in amperes"
    },
    "load_regulation": {
      "type": "object",
      "description": "Load regulation test results",
      "properties": {
        "no_load_voltage": {"type": "number"},
        "full_load_voltage": {"type": "number"},
        "regulation_percent": {"type": "number"}
      },
      "required": ["no_load_voltage", "full_load_voltage", "regulation_percent"]
    },
    "ripple_analysis": {
      "type": "object",
      "description": "AC ripple measurements",
      "properties": {
        "peak_to_peak_mv": {"type": "number"},
        "rms_mv": {"type": "number"},
        "frequency_hz": {"type": "number"},
        "harmonics": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "harmonic_number": {"type": "integer"},
              "amplitude_mv": {"type": "number"},
              "frequency_hz": {"type": "number"}
            }
          }
        }
      },
      "required": ["peak_to_peak_mv", "rms_mv"]
    },
    "transient_response": {
      "type": "object",
      "description": "Load transient response characteristics",
      "properties": {
        "overshoot_mv": {"type": "number"},
        "undershoot_mv": {"type": "number"},
        "settling_time_us": {"type": "number"},
        "recovery_time_us": {"type": "number"}
      },
      "required": ["overshoot_mv", "settling_time_us"]
    },
    "efficiency": {
      "type": "object",
      "description": "Power conversion efficiency measurements",
      "properties": {
        "input_power_watts": {"type": "number"},
        "output_power_watts": {"type": "number"},
        "efficiency_percent": {"type": "number"}
      },
      "required": ["input_power_watts", "output_power_watts", "efficiency_percent"]
    }
  },
  "required": ["output_voltage", "output_current", "load_regulation", "ripple_analysis"]
}
```

This schema captures a complete power supply characterization where all measurements are logically related but would be awkward to represent as separate scalar or vector measurements. The hierarchical structure preserves the semantic relationships between the different aspects of the power supply performance.

## Error Handling

### Common Error Scenarios

1. **Schema not found**
   ```
   Code: FAILED_PRECONDITION
   Message: "Schema with id 'abc-123' not found. Ensure schema is registered before publishing measurements."
   ```

2. **Schema validation failure**
   ```
   Code: INVALID_ARGUMENT
   Message: "JSON value does not conform to schema 'abc-123': Missing required property 'output_voltage'"
   ```

3. **Missing schema_id**
   ```
   Code: INVALID_ARGUMENT
   Message: "JsonValue.schema_id is required"
   ```

4. **Missing value**
   ```
   Code: INVALID_ARGUMENT
   Message: "JsonValue.value is required"
   ```
