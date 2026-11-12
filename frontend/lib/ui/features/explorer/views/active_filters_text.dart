/// The empty state's list of active filters (DESIGN.md §7: "Filtros
/// activos: estado En precio · arquetipo Ancla Defensiva."), in the order
/// of the preview: search, status, position, archetype.
library;

import '../../../../routing/explorer_query.dart';
import '../../../core/labels/archetypes.dart';
import '../../../core/labels/positions.dart';
import '../../../core/labels/valuation_labels.dart';

/// The active filters of [query], joined with " · ".
String describeActiveFilters(ExplorerQuery query) => [
  if (query.search case final search?) 'búsqueda «$search»',
  if (query.status case final status?) 'estado ${valuationStatusLabel(status)}',
  if (positionLabel(query.position) case final position?) 'posición $position',
  if (archetypeShortName(query.clusterId) case final archetype?)
    'arquetipo $archetype',
].join(' · ');
