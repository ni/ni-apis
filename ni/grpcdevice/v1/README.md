# grpd-device .proto files

This repository contains several `.proto` files. These files are here because the ones in the [grpc-device GitHub repository](https://github.com/ni/grpc-device/tree/main/imports/protobuf) are not following our current conventions and style for `.proto` files. For example, they have the 'grpc_device' package name but are not in a folder of that name. They don't include the 'ni' package name.

Since some of the other .proto files in this repository reference the grpc-device .proto files, we are including our own copy of these `.proto` files in this repository. We point to the 'ni/grpcdevice/v1' directory as an include path when we compile the other .proto files.

See the [NI gRPC Protocol Buffer Style Guide](https://dev.azure.com/ni/DevCentral/_wiki/wikis/AppCentral.wiki/37475/NI-gRPC-Protocol-Buffer-Style-Guide) for details.