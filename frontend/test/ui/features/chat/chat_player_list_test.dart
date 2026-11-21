// Widget and DTO tests for the clickable player cards shown inside PitIA's
// bubble on both live SSE answers and restored saved conversations.
import 'dart:convert';

import 'package:delphos_frontend/data/models/chat_referenced_player_dto.dart';
import 'package:delphos_frontend/ui/core/widgets/flag_image.dart';
import 'package:delphos_frontend/ui/core/widgets/player_avatar.dart';
import 'package:delphos_frontend/ui/core/widgets/remote_logo.dart';
import 'package:delphos_frontend/ui/core/widgets/status_text.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_player_list.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/chat_session_fixtures.dart';
import '../../../support/explorer_harness.dart';

Map<String, Object?> _cubarsiJson() => {
  'player_id': 1025,
  'name': 'Pau Cubarsí',
  'position': 'Defender',
  'sub_position': 'Centre-Back',
  'country': 'Spain',
  'club_name': 'FC Barcelona',
  'club_logo_url': 'https://tmssl.akamaized.net/images/wappen/head/131.png',
  'league_id': 'ES1',
  'image_url': 'https://img.a.transfermarkt.technology/portrait/header/962110-1710751908.jpg',
  'market_value_eur': 70000000.0,
  'fair_value_eur': 95000000.0,
  'valuation_status': 'undervalued',
};

void main() {
  setUp(ChatIntroGate.reset);

  test('DTO allowlists image URLs and ignores malformed items safely', () {
    final parsed = ChatReferencedPlayerDto.parseList([
      {
        ..._cubarsiJson(),
        'image_url': 'https://evil.example/steal.jpg',
        'club_logo_url': 'http://tmssl.akamaized.net/plain-http.png',
      },
      {'bad': 'shape'},
      'not-a-map',
    ]);

    expect(parsed.length, 1);
    expect(parsed[0].id, 1025);
    expect(parsed[0].imageUrl, isNull);
    expect(parsed[0].clubLogoUrl, isNull);
  });

  testWidgets(
    'live message with hydrated players renders avatar, flag, league logo and opens dossier',
    (tester) async {
      final ssePayload = jsonEncode({
        'session_id': 'sess-players',
        'message': '**Pau Cubarsí** destaca en defensa.',
        'model_run_id': 'run_test',
        'tools_called': ['get_player_profile'],
        'created_at': '2026-11-20T12:00:00Z',
        'players': [_cubarsiJson()],
      });
      final backend = FakePlayersBackend()
        ..chatSseBody =
            'event: tool\n'
            'data: {"tool":"get_player_profile","ok":true,"summary":"Perfil de Pau Cubarsí."}\n\n'
            'event: message\n'
            'data: $ssePayload\n\n';
      final router = await pumpAppAt(tester, '/chat', backend: backend);

      await tester.tap(find.text('Entendido'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Analiza a Cubarsí');
      await tester.tap(find.text('Enviar'));
      await tester.pumpAndSettle();

      final list = find.byType(ChatPlayerList);
      expect(list, findsOneWidget);
      expect(
        find.descendant(of: list, matching: find.text('Jugadores mencionados')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.byType(PlayerAvatar)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.byType(FlagImage)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.byType(RemoteLogo)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.byType(StatusText)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.text('Pau Cubarsí')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: list,
          matching: find.text('FC Barcelona · Defensa central'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(of: list, matching: find.text('Infravalorado')),
        findsOneWidget,
      );

      await tester.tap(
        find.descendant(of: list, matching: find.text('Pau Cubarsí')),
      );
      await tester.pumpAndSettle();

      expect(currentPath(router), '/explorador');
      expect(
        router
            .routerDelegate
            .currentConfiguration
            .uri
            .queryParameters['jugador'],
        '1025',
      );
    },
  );

  testWidgets('restored saved conversation renders hydrated player cards too', (
    tester,
  ) async {
    const sessionId = '11111111-1111-4111-8111-111111111111';
    final backend = FakePlayersBackend()
      ..chatSessions = [chatSessionJson(sessionId, title: 'Analiza a Cubarsí')]
      ..chatMessages[sessionId] = [
        chatMessageJson('user', 'Analiza a Cubarsí', n: 1),
        chatMessageJson(
          'assistant',
          '**Pau Cubarsí** mantiene alto rendimiento.',
          n: 2,
          players: [
            {..._cubarsiJson(), 'league_id': 'UNKNOWN_LEAGUE'},
          ],
        ),
      ];
    await pumpAppAt(tester, '/chat', backend: backend);

    await tester.tap(find.text('Entendido'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Conversaciones'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Analiza a Cubarsí'));
    await tester.pumpAndSettle();

    expect(find.byType(ChatPlayerList), findsOneWidget);
    expect(find.text('Pau Cubarsí'), findsOneWidget);
    final logo = tester.widget<RemoteLogo>(find.byType(RemoteLogo));
    expect(logo.url, isNull);
  });
}
