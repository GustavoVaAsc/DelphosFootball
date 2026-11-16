/// The selector's floating list (DESIGN.md §5: shadow only on what
/// floats): each suggestion shows the name in the condensed cut, then the
/// club and the market price; the pointer's hover uses the subtle ground and
/// the keyboard highlight the selected-row tint. While a search runs, fails or
/// finds nobody, the list says so in one plain line.
library;

import 'package:flutter/widgets.dart';

import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_shadows.dart';
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
        ? 'Ningún jugador coincide con la búsqueda.'
        : null;
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(vertical: 4),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(DelphosRadius.control),
        border: Border.all(color: DelphosColors.rule),
        boxShadow: DelphosShadows.float,
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
                  _SuggestionRow(
                    key: ValueKey(vm.results[i].id),
                    highlighted: i == vm.highlighted,
                    name: vm.results[i].name,
                    detail: [
                      ?vm.results[i].clubName,
                      formatEur(vm.results[i].marketValueEur),
                    ].join(' · '),
                    onTap: () => onPick(vm.results[i].id),
                  ),
              ],
            ),
    );
  }
}

class _SuggestionRow extends StatefulWidget {
  const _SuggestionRow({
    super.key,
    required this.highlighted,
    required this.name,
    required this.detail,
    required this.onTap,
  });

  final bool highlighted;
  final String name;
  final String detail;
  final VoidCallback onTap;

  @override
  State<_SuggestionRow> createState() => _SuggestionRowState();
}

class _SuggestionRowState extends State<_SuggestionRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    // The keyboard highlight wins over the hover ground.
    final ground = widget.highlighted
        ? DelphosColors.selectedBg
        : (_hovered ? DelphosColors.surfaceSubtle : null);
    return Semantics(
      button: true,
      selected: widget.highlighted,
      child: GestureDetector(
        onTap: widget.onTap,
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          onEnter: (_) => setState(() => _hovered = true),
          onExit: (_) => setState(() => _hovered = false),
          child: Container(
            color: ground,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.name, style: DelphosText.condensed()),
                Text(
                  widget.detail,
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
    );
  }
}
