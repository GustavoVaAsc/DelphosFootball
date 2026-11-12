/// The table's empty state (DESIGN.md §7): it names the active filters and
/// offers the one way out, "Restablecer filtros".
library;

import 'package:flutter/widgets.dart';

import '../../../../routing/explorer_query.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';
import 'active_filters_text.dart';

/// "Ningún jugador cumple estos filtros" with the filters it names.
class EmptyResultPanel extends StatelessWidget {
  const EmptyResultPanel({
    super.key,
    required this.query,
    required this.onReset,
  });

  final ExplorerQuery query;
  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) => StatePanel(
    title: 'Ningún jugador cumple estos filtros',
    text: 'Filtros activos: ${describeActiveFilters(query)}.',
    action: ActionButton(label: 'Restablecer filtros', onPressed: onReset),
  );
}
