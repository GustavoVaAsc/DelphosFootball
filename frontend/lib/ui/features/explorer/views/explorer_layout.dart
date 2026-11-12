/// The explorer's arrangement (DESIGN.md §4, Master-detail split): the
/// filter bar on top; below it the table alone, the table with the 440 px
/// dossier beside it, the dossier alone on a narrow window, or the one
/// error panel across the whole explorer.
library;

import 'package:flutter/widgets.dart';

import '../../../core/layout/dossier_presentation.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';
import '../view_models/dossier_view_model.dart';
import '../view_models/explorer_status.dart';
import '../view_models/explorer_view_model.dart';
import 'dossier_panel.dart';
import 'filter_bar.dart';
import 'players_table.dart';
import 'row_focus_registry.dart';

/// Lays out view 1 for the current state.
class ExplorerLayout extends StatelessWidget {
  const ExplorerLayout({
    super.key,
    required this.vm,
    required this.dossier,
    required this.presentation,
    required this.rowFocus,
    required this.tableFocus,
    required this.searchFocus,
    required this.dossierFocus,
    required this.onRetry,
    this.datasetTotal,
  });

  final ExplorerViewModel vm;
  final DossierViewModel dossier;
  final DossierPresentation presentation;
  final RowFocusRegistry rowFocus;
  final FocusNode tableFocus;
  final FocusNode searchFocus;
  final FocusNode dossierFocus;
  final VoidCallback onRetry;
  final int? datasetTotal;

  @override
  Widget build(BuildContext context) {
    final Widget content;
    if (vm.status == ExplorerStatus.error) {
      // The dossier stays closed while the data is unreachable (§7).
      content = DecoratedBox(
        decoration: BoxDecoration(
          color: DelphosColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: DelphosColors.rule),
        ),
        child: StatePanel(
          title: 'No se pudo conectar con el servidor de datos',
          text:
              'Los datos del mercado no están disponibles ahora mismo. '
              'Comprueba la conexión e inténtalo de nuevo.',
          action: ActionButton(
            label: 'Reintentar',
            primary: true,
            onPressed: onRetry,
          ),
        ),
      );
    } else {
      final table = PlayersTable(
        vm: vm,
        rowFocus: rowFocus,
        tableFocus: tableFocus,
        datasetTotal: datasetTotal,
      );
      final panel = Focus(
        focusNode: dossierFocus,
        child: DossierPanel(vm: dossier, onClose: vm.closeDossier),
      );
      content = switch ((vm.query.isDossierOpen, presentation)) {
        (false, _) => table,
        (true, DossierPresentation.fullPage) => panel,
        (true, DossierPresentation.sidePanel) => Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          spacing: 20,
          children: [
            Expanded(child: table),
            SizedBox(width: 440, child: panel),
          ],
        ),
      };
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilterBar(vm: vm, searchFocus: searchFocus),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
            child: content,
          ),
        ),
      ],
    );
  }
}
