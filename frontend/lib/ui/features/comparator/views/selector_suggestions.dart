/// The selector's floating list (DESIGN.md §5: shadow only on what
/// floats): each suggestion shows the name, then the club and the market
/// price; the keyboard highlight uses the selected-row tint. While a search
/// runs, fails or finds nobody, the list says so in one plain line.
library;

import 'package:flutter/widgets.dart';

import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../view_models/player_search_view_model.dart';

/// The suggestions for the current search.
class SelectorSuggestions extends StatelessWidget {
  const SelectorSuggestions({
    super.key,
    required this.vm,
    required this.width,
    required this.onPick,
  });

  final PlayerSearchViewModel vm;
  final double width;
  final ValueChanged<int> onPick;

  @override
  Widget build(BuildContext context) {
    final muted = DelphosText.ui(color: DelphosColors.ink2);
    final String? message = vm.isLoading && vm.results.isEmpty
        ? 'Buscando…'
        : vm.failed
        ? 'No se pudo buscar ahora mismo.'
        : vm.results.isEmpty
        ? 'Ningún jugador con ese nombre.'
        : null;
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(vertical: 4),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: DelphosColors.rule),
        boxShadow: const [
          BoxShadow(
            color: DelphosColors.floatShadow,
            offset: Offset(0, 2),
            blurRadius: 6,
          ),
        ],
      ),
      child: message != null
          ? Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Text(message, style: muted),
            )
          : Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (var i = 0; i < vm.results.length; i++)
                  Semantics(
                    button: true,
                    selected: i == vm.highlighted,
                    child: GestureDetector(
                      onTap: () => onPick(vm.results[i].id),
                      child: MouseRegion(
                        cursor: SystemMouseCursors.click,
                        child: Container(
                          color: i == vm.highlighted
                              ? DelphosColors.selectedBg
                              : null,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 6,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                vm.results[i].name,
                                style: DelphosText.ui(weight: FontWeight.w600),
                              ),
                              Text(
                                [
                                  ?vm.results[i].clubName,
                                  formatEur(vm.results[i].marketValueEur),
                                ].join(' · '),
                                style: DelphosText.ui(
                                  size: TypeScale.secondary,
                                  color: DelphosColors.ink2,
                                  tabular: true,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}
