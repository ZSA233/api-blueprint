import 'dart:convert';
import 'dart:typed_data';

import 'package:api_blueprint_example/api_blueprint_example.dart';
import 'package:test/test.dart';

void main() {
  test('binary schema codecs round trip packet fields', () {
    final payload = Uint8List.fromList(utf8.encode('abc'));
    final label = Uint8List.fromList(utf8.encode('A'));
    final packet = DemoPacket(
      flags: DemoPacketFlagsValues.hasPayload | DemoPacketFlagsValues.hasScores,
      shortCode: 7,
      signedDelta: 1,
      itemCount: 1,
      payloadLen: payload.length,
      items: [
        DemoPacketItem(
          id: 1,
          enabled: true,
          value: 1.5,
          labelLen: label.length,
          label: label,
        ),
      ],
      payload: payload,
      scores: const [1.0, 2.0],
      checksum: 1 + payload.length,
    );

    final bytes = encodeDemoPacket(packet);
    final decoded = decodeDemoPacket(bytes);

    expect(bytes.length, greaterThan(0));
    expect(decoded.version, 1);
    expect(decoded.kind, DemoPacketKindValues.metric);
    expect(decoded.flags, packet.flags);
    expect(decoded.payload, payload);
    expect(decoded.items?.single.id, 1);
    expect(decoded.items?.single.enabled, isTrue);
    expect(decoded.items?.single.label, label);
    expect(decoded.checksum, packet.checksum);
  });
}
