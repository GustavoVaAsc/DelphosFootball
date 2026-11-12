/// The market table card (DESIGN.md §4 and §7): sticky header, rows built
/// lazily at a fixed 65 px extent, and the footer. Loading shows eight
/// static skeleton rows; an empty result names the active filters.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/widgets/inset_focus_frame.dart';
import '../view_models/explorer_status.dart';
import '../view_models/explorer_view_model.dart';
import 'empty_result_panel.dart';
import 'player_row.dart';
import 'row_focus_registry.dart';
import 'skeleton_row.dart';
import 'table_footer.dart';
import 'table_footer_text.dart';
import 'table_header.dart';

/// The ledger, its states and its pager.
class PlayersTable extends StatefulWidget {
  const PlayersTable({
    super.key,
    required this.vm,
    required this.rowFocus,
    required this.tableFocus,
    this.datasetTotal,
  });

  final ExplorerViewModel vm;
  final RowFocusRegistry rowFocus;

  /// Where focus lands when the dossier closes and its row is gone.
  final FocusNode tableFocus;
  final int? datasetTotal;

  @override
  State<PlayersTable> createState() => _PlayersTableState();
}

class _PlayersTableState extends State<PlayersTable> {
  final ScrollController _scroll = ScrollController();
  int? _shownPage;

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  /// A new page starts at its top row.
  void _scrollToTopOnNewPage() {
    final page = widget.vm.page;
    final key = page == null ? null : Object.hash(page.page, page.total);
    if (key == _shownPage) return;
    _shownPage = key;
    // After the frame: jumping notifies scroll listeners, not allowed mid-build.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scroll.hasClients) _scroll.jumpTo(0);
    });
  }

  @override
  Widget build(BuildContext context) {
    final vm = widget.vm;
    final page = vm.page;
    final open = vm.query.isDossierOpen;
    _scrollToTopOnNewPage();
    final Widget body;
    final String footer;
    if (vm.status == ExplorerStatus.loading || page == null) {
      footer = 'Cargando jugadores…';
      body = Column(
        children: [for (var i = 0; i < 8; i++) SkeletonRow(dossierOpen: open)],
      );
    } else if (vm.status == ExplorerStatus.empty) {
      footer = tableFooterText(
        total: 0,
        page: 1,
        pageSize: page.pageSize,
        datasetTotal: widget.datasetTotal,
      );
      body = EmptyResultPanel(query: vm.query, onReset: vm.resetFilters);
    } else {
      footer = vm.isRefreshing
          ? 'Cargando jugadores…'
          : tableFooterText(
              total: page.total,
              page: page.page,
              pageSize: page.pageSize,
              datasetTotal: widget.datasetTotal,
            );
      widget.rowFocus.retainOnly({for (final p in page.players) p.id});
      body = ListView.builder(
        controller: _scroll,
        itemExtent: PlayerRow.extent,
        itemCount: page.players.length,
        itemBuilder: (context, index) {
          final player = page.players[index];
          return PlayerRow(
            key: ValueKey(player.id),
            player: player,
            selected: open && vm.query.playerId == player.id,
            dossierOpen: open,
            onToggle: () => vm.togglePlayer(player.id),
            nameFocusNode: widget.rowFocus.nodeFor(player.id),
          );
        },
      );
    }
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        children: [
          if (vm.status != ExplorerStatus.empty) TableHeader(dossierOpen: open),
          Expanded(
            child: InsetFocusFrame(focusNode: widget.tableFocus, child: body),
          ),
          TableFooter(
            text: footer,
            page: page?.page ?? 1,
            totalPages: page?.totalPages ?? 1,
            onPage: vm.status == ExplorerStatus.ready ? vm.goToPage : null,
          ),
        ],
      ),
    );
  }
}
