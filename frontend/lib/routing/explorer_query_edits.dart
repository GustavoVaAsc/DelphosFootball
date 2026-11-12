/// Building a changed explorer query, for the ViewModel's filter, page and
/// dossier actions. Kept apart from `explorer_query.dart`, which parses and
/// writes the URL, so neither file outgrows the module budget.
library;

import '../domain/models/valuation_status.dart';
import 'explorer_query.dart';

const Object _keep = Object();

/// Copies with one or more fields replaced; pass `null` to clear a field.
extension ExplorerQueryEdits on ExplorerQuery {
  ExplorerQuery copyWith({
    Object? status = _keep,
    Object? position = _keep,
    Object? clusterId = _keep,
    Object? search = _keep,
    int? page,
    Object? playerId = _keep,
  }) => ExplorerQuery(
    status: identical(status, _keep) ? this.status : status as ValuationStatus?,
    position: identical(position, _keep) ? this.position : position as String?,
    clusterId: identical(clusterId, _keep) ? this.clusterId : clusterId as int?,
    search: identical(search, _keep) ? this.search : search as String?,
    page: page ?? this.page,
    playerId: identical(playerId, _keep) ? this.playerId : playerId as int?,
  );
}
