/// The explorer's arrangement (DESIGN.md §4, Master-detail split): the
/// filter bar on top; below it the table alone, the table with the 440 px
/// dossier beside it, the dossier alone on a narrow window, or the one
/// error panel across the whole explorer.
library;

import 'package:flutter/widgets.dart';

import '../../../core/layout/dossier_presentation.dart';
import '../../../core/widgets/enter_motion.dart';
import '../view_models/dossier_view_model.dart';
import '../view_models/explorer_status.dart';
import '../view_models/explorer_view_model.dart';
import 'dossier_panel.dart';
import 'dossier_slot.dart';
import 'explorer_error_panel.dart';
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
    this.onDossierExited,
    this.dossierExiting = false,
    this.staggerFirstLoad = false,
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

  /// Called when the side panel has finished leaving.
  final VoidCallback? onDossierExited;

  /// Whether a close is playing the side panel's exit.
  final bool dossierExiting;

  /// Whether the table rows of its first load enter staggered.
  final bool staggerFirstLoad;
  final int? datasetTotal;

  @override
  Widget build(BuildContext context) {
    final Widget content;
    if (vm.status == ExplorerStatus.error) {
      // The dossier stays closed while the data is unreachable (§7).
      content = ExplorerErrorPanel(onRetry: onRetry);
    } else {
      // While the side panel is still leaving, the table keeps the open
      // layout and the selected row; it takes the width back when the exit
      // ends (DESIGN.md §5).
      final exiting =
          dossierExiting && presentation == DossierPresentation.sidePanel;
      final table = PlayersTable(
        vm: vm,
        dossierOpen: vm.query.isDossierOpen || exiting,
        selectedId: vm.query.playerId ?? (exiting ? dossier.playerId : null),
        rowFocus: rowFocus,
        tableFocus: tableFocus,
        datasetTotal: datasetTotal,
        staggerFirstLoad: staggerFirstLoad,
      );
      // Rebuilds the panel alone on a dossier notification; the table and
      // filter bar depend only on [vm].
      final panel = Focus(
        focusNode: dossierFocus,
        child: ListenableBuilder(
          listenable: dossier,
          builder: (context, _) =>
              DossierPanel(vm: dossier, onClose: vm.closeDossier),
        ),
      );
      final sidePanel =
          vm.query.isDossierOpen &&
          presentation == DossierPresentation.sidePanel;
      content = vm.query.isDossierOpen && !sidePanel
          // The full-page dossier only fades in (DESIGN.md §5).
          ? EnterMotion(child: panel)
          : Row(
              // The table is always the Row's first child, so opening and
              // closing the side panel keeps its State and scroll offset.
              // The slot holds the panel through its exit animation.
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: table),
                DossierSlot(
                  open: sidePanel,
                  onExited: onDossierExited,
                  child: panel,
                ),
              ],
            );
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
