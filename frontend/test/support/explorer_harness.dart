// A fake backend for the explorer: generated /players pages, the three
// dossier endpoints per player, /clusters and /reports; requests it can
// hold and release in any order, and a failure switch.
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:delphos_frontend/data/services/api_client.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'cluster_fixtures.dart';
import 'dossier_fixtures.dart';
import 'http_fakes.dart';
import 'report_fixtures.dart';

class FakePlayersBackend {
  FakePlayersBackend() {
    api = ApiClient(baseUrl: testBaseUrl, httpClient: MockClient(_handle));
  }

  late final ApiClient api;
  final List<Uri> requests = [];
  int total = 5522;
  bool failNext = false;
  bool hold = false;

  /// Fails every /clusters request while true.
  bool failClusters = false;

  /// Answers /players/{id}/replacements with a 404.
  bool replacementsMissing = false;

  /// Candidates per replacements answer, and the shortfall code.
  int replacementsCount = 3;
  String? shortfall;

  /// Answers POST /chat with a 503 RFC 9457 error while true.
  bool chatUnavailable = false;

  /// Optional custom SSE body returned by POST /chat when `chatUnavailable` is false.
  String? chatSseBody;

  /// The report `GET /reports` lists for any player; none when `null`.
  Map<String, Object?>? storedReport;
  final List<Completer<void>> _held = [];

  /// Rows on page 1 with the current total.
  int get idsPerPage => math.min(50, total);

  /// The id of row [index] on page 1 without a search.
  int idOnPage(int index) => _baseId(1, null) + index;

  int _baseId(int page, String? search) =>
      1000 * page + (search == null ? 0 : 500000);

  Future<http.Response> _handle(http.Request request) async {
    requests.add(request.url);
    // The failure switch hits the player list only, never /clusters.
    if (failNext && request.url.pathSegments.join('/') == 'players') {
      failNext = false;
      throw http.ClientException('offline', request.url);
    }
    if (hold) {
      final gate = Completer<void>();
      _held.add(gate);
      await gate.future;
    }
    final segments = request.url.pathSegments;
    if (failClusters && segments.join('/') == 'clusters') {
      throw http.ClientException('offline', request.url);
    }
    if (replacementsMissing &&
        segments.length == 3 &&
        segments.last == 'replacements') {
      return problemResponse(404, 'Not Found', 'none');
    }
    if (segments.length == 1 && segments.first == 'chat') {
      if (chatUnavailable) {
        return problemResponse(
          503,
          'Service Unavailable',
          'Chat inference service unavailable',
        );
      }
      final body = chatSseBody ?? _defaultChatSse();
      return http.Response.bytes(
        utf8.encode(body),
        200,
        headers: {'content-type': 'text/event-stream; charset=utf-8'},
      );
    }
    return jsonResponse(switch (segments) {
      ['clusters'] => clustersJson(),
      ['reports'] => reportListJson([?storedReport]),
      ['reports', 'generate'] => reportJson(
        'deterministic',
        playerId: (jsonDecode(request.body) as Map)['player_id'] as int,
      ),
      ['players', final id, 'replacements'] => replacementsJson(
        int.parse(id),
        count: replacementsCount,
        shortfall: shortfall,
      ),
      ['players', _] || ['players', _, _] => dossierJsonFor(request.url.path),
      _ => _pageJson(request.url.queryParameters),
    });
  }

  Map<String, Object?> _pageJson(Map<String, String> params) {
    final page = int.parse(params['page'] ?? '1');
    final size = int.parse(params['page_size'] ?? '20');
    final search = params['name'];
    final count = math.max(0, math.min(size, total - (page - 1) * size));
    final base = _baseId(page, search);
    return {
      'model_run_id': 'run_test',
      'items': [
        for (var i = 0; i < count; i++)
          {
            'player_id': base + i,
            'name': '${search ?? 'Jugador'} ${base + i}',
            'last_name': 'Apellido',
            'position': 'Attack',
            'sub_position': 'Right Winger',
            'country_of_citizenship': 'France',
            'club_name': 'Club',
            'market_value_eur': 1e6,
            'valuation_status': 'fair',
            'cluster_id': 0,
          },
      ],
      'total': total,
      'page': page,
      'page_size': size,
      'total_pages': total == 0 ? 0 : (total / size).ceil(),
    };
  }

  String _defaultChatSse() =>
      'event: tool\n'
      'data: {"tool":"search_players","ok":true,"summary":"Se consultaron 2 jugadores en el mercado."}\n\n'
      'event: tool\n'
      'data: {"tool":"get_player_valuation","ok":true,"summary":"Se revisó la valoración y el diagnóstico de Harry Kane."}\n\n'
      'event: message\n'
      'data: {"session_id":"sess-1","message":"Harry Kane presenta infravaloración en la temporada 2025/26.","model_run_id":"run_test","tools_called":["search_players","get_player_valuation"],"created_at":"2026-11-13T12:00:00Z"}\n\n';

  /// Answers every held request in arrival order.
  void release() {
    hold = false;
    for (final gate in _held) {
      gate.complete();
    }
    _held.clear();
  }

  /// Answers every held request, newest first.
  void releaseInReverse() {
    hold = false;
    for (final gate in _held.reversed) {
      gate.complete();
    }
    _held.clear();
  }

  /// Lets pending responses reach the ViewModel.
  Future<void> settle() async {
    for (var i = 0; i < 5; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }
}
