// Tests that opening and closing the dossier each send one polite
// announcement ("Ficha de X abierta", "Ficha cerrada"), and that a page load
// sends none.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';

void main() {
  testWidgets('opening and closing announce once each, not on load', (
    tester,
  ) async {
    final messages = <String>[];
    tester.binding.defaultBinaryMessenger.setMockDecodedMessageHandler(
      SystemChannels.accessibility,
      (message) async {
        final data = (message as Map)['data'] as Map;
        if (message['type'] == 'announce') {
          messages.add(data['message'] as String);
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockDecodedMessageHandler(
        SystemChannels.accessibility,
        null,
      ),
    );
    await pumpAppAt(tester, '/explorador');
    expect(messages, isEmpty);
    await tester.tap(find.text('Jugador 1000'));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(messages, ['Ficha de Jugador 1000 abierta', 'Ficha cerrada']);
  });
}
