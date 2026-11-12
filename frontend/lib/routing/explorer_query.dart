/// The explorer's state as it lives in the URL (ADR-024):
/// `/explorador?estado=&posicion=&arquetipo=&q=&pagina=&jugador=<id>`.
///
/// Parameter names and values are Spanish, so a shared link reads as the
/// product does. An unknown or malformed value is dropped rather than
/// rejected: a stale bookmark opens the explorer with fewer filters, never
/// an error page. A search above [ExplorerQuery.maxSearchLength] characters
/// and an id outside `parseRouteId` are dropped too. The dossier is open
/// exactly when `jugador` is present.
library;

import '../domain/models/player_query.dart';
import '../domain/models/valuation_status.dart';
import 'route_params.dart';
import 'routes.dart';

/// The filters, page and open player of the explorer.
class ExplorerQuery {
  const ExplorerQuery({
    this.status,
    this.position,
    this.clusterId,
    this.search,
    this.page = 1,
    this.playerId,
  });

  factory ExplorerQuery.fromQueryParameters(Map<String, String> params) {
    final search = params['q']?.trim();
    return ExplorerQuery(
      status: _statusSlugs.entries
          .where((entry) => entry.value == params['estado'])
          .firstOrNull
          ?.key,
      position: _positionSlugs.entries
          .where((entry) => entry.value == params['posicion'])
          .firstOrNull
          ?.key,
      clusterId: parseRouteId(params['arquetipo']),
      search:
          search == null || search.isEmpty || search.length > maxSearchLength
          ? null
          : search,
      page: switch (parseRouteId(params['pagina'])) {
        final page? when page >= 1 => page,
        _ => 1,
      },
      playerId: switch (parseRouteId(params['jugador'])) {
        final id? when id >= 1 => id,
        _ => null,
      },
    );
  }

  /// The longest search the URL may carry; a longer one is dropped.
  static const int maxSearchLength = 100;

  /// Rows per table page.
  static const int pageSize = 50;

  static const Map<ValuationStatus, String> _statusSlugs = {
    ValuationStatus.undervalued: 'infravalorado',
    ValuationStatus.fair: 'en-precio',
    ValuationStatus.overvalued: 'sobrevalorado',
  };

  /// The dataset's English position keys and their URL slugs.
  static const Map<String, String> _positionSlugs = {
    'Attack': 'ataque',
    'Midfield': 'mediocampo',
    'Defender': 'defensa',
  };

  final ValuationStatus? status;

  /// The dataset's English position key ("Attack").
  final String? position;
  final int? clusterId;
  final String? search;

  /// The 1-based table page.
  final int page;

  /// The player whose dossier is open, if any.
  final int? playerId;

  bool get isDossierOpen => playerId != null;

  /// Whether any filter narrows the list ("Restablecer filtros" is enabled).
  bool get hasFilters =>
      status != null || position != null || clusterId != null || search != null;

  /// Whether [other] lists the same rows; only the open player may differ.
  bool sameListAs(ExplorerQuery other) =>
      status == other.status &&
      position == other.position &&
      clusterId == other.clusterId &&
      search == other.search &&
      page == other.page;

  /// The URL query parameters, without the defaults.
  Map<String, String> toQueryParameters() => {
    'estado': ?_statusSlugs[status],
    'posicion': ?_positionSlugs[position],
    if (clusterId case final clusterId?) 'arquetipo': '$clusterId',
    'q': ?search,
    if (page != 1) 'pagina': '$page',
    if (playerId case final playerId?) 'jugador': '$playerId',
  };

  /// The explorer URL for this query, defaults left out.
  String toLocation() {
    final params = toQueryParameters();
    return Uri(
      path: Routes.explorer,
      queryParameters: params.isEmpty ? null : params,
    ).toString();
  }

  /// The repository request for the table.
  PlayerQuery toPlayerQuery() => PlayerQuery(
    name: search,
    position: position,
    valuationStatus: status,
    clusterId: clusterId,
    page: page,
    pageSize: pageSize,
  );
}
