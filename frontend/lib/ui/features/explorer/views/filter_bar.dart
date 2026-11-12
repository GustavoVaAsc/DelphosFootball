/// The explorer's filter bar (DESIGN.md §4): search, Estado, Posición,
/// Arquetipo, then "Restablecer filtros", enabled only when a filter is
/// active. One row at 1440 px; on narrower windows the controls wrap to a
/// second line instead of overflowing.
library;

import 'package:flutter/widgets.dart';

import '../../../core/labels/archetypes.dart';
import '../../../core/labels/positions.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import '../view_models/explorer_status.dart';
import '../view_models/explorer_view_model.dart';
import 'filter_select.dart';
import 'search_field.dart';
import 'status_segments.dart';

/// The filter controls, wired to the explorer's ViewModel.
class FilterBar extends StatelessWidget {
  const FilterBar({super.key, required this.vm, required this.searchFocus});

  final ExplorerViewModel vm;
  final FocusNode searchFocus;

  @override
  Widget build(BuildContext context) {
    final query = vm.query;
    // Filters are disabled until the first page answers (DESIGN.md §7).
    final ready =
        vm.page != null &&
        vm.status != ExplorerStatus.error &&
        vm.status != ExplorerStatus.loading;
    final controls = <Widget>[
      SearchField(
        text: vm.searchText,
        enabled: ready,
        focusNode: searchFocus,
        onChanged: vm.setSearchText,
      ),
      Row(
        mainAxisSize: MainAxisSize.min,
        spacing: 8,
        children: [
          ExcludeSemantics(
            child: Text(
              'Estado',
              style: DelphosText.ui(
                size: TypeScale.secondary,
                weight: FontWeight.w500,
                color: DelphosColors.ink3,
              ),
            ),
          ),
          StatusSegments(
            value: query.status,
            onChanged: ready ? vm.setStatusFilter : null,
          ),
        ],
      ),
      FilterSelect<String>(
        label: 'Posición',
        value: query.position,
        options: [
          (null, 'Todas'),
          for (final key in const ['Attack', 'Midfield', 'Defender'])
            (key, positionLabel(key)!),
        ],
        onChanged: ready ? vm.setPosition : null,
      ),
      FilterSelect<int>(
        label: 'Arquetipo',
        value: query.clusterId,
        options: [
          (null, 'Todos'),
          for (final id in const [0, 1, 2]) (id, archetypeShortName(id)!),
        ],
        onChanged: ready ? vm.setCluster : null,
      ),
    ];
    final reset = ActionButton(
      label: 'Restablecer filtros',
      onPressed: query.hasFilters || vm.searchText.trim().isNotEmpty
          ? vm.resetFilters
          : null,
    );
    return Semantics(
      container: true,
      label: 'Filtros de jugadores',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
        decoration: const BoxDecoration(
          color: DelphosColors.surface,
          border: Border(bottom: BorderSide(color: DelphosColors.rule)),
        ),
        // The controls wrap to a second line when the window is narrower
        // than 1440 px; the reset button keeps its place on the right.
        child: Row(
          spacing: 14,
          children: [
            Expanded(
              child: Wrap(
                spacing: 14,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: controls,
              ),
            ),
            reset,
          ],
        ),
      ),
    );
  }
}
