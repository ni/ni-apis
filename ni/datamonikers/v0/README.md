# Data Moniker V0 APIs

This API predates the NI gRPC Protocol Buffer Style Guide and creation of this 
repository, so it does not follow our current conventions and style for `.proto` 
files. For example, the package name does not contain a version number and a
number of the request and response message names do not follow current conventions.

Because this API does not follow standard package naming and versioning guidelines,
when you run `protoc` on this API or other APIs that depend on it, you may need to
add `ni/datamonikers/v0` to the include path in order to satisfy import directives
such as `import "data_moniker.proto"`.

This file originated from:
- Git repo: https://github.com/ni/grpc-device/blob/main/imports/protobuf/data_moniker.proto
- Commit hash: e6081e83d9a075a4b74fd5722ff458fcf42c1e55
