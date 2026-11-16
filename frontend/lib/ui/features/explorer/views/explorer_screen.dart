/// The Explorador de Mercado (DESIGN.md §4): the filter bar over the market
/// table, and the player dossier beside it (from 1100 px) or in its place
/// (narrower windows, ADR-027). The URL drives everything (ADR-024).
library;

import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../routing/explorer_query.dart';
import '../../../core/layout/dossier_presentation.dart';
import '../../../core/util/first_load_tracker.dart';
import '../../../core/view_models/dataset_view_model.dart';
import '../view_models/dossier_view_model.dart';
import '../view_models/explorer_view_model.dart';
import 'dossier_announcement.dart';
import 'dossier_exit.dart';
import 'explorer_layout.dart';
import 'explorer_focus.dart';

/// The explorer page for the filters and open player in [query].
class ExplorerScreen extends StatefulWidget {
  const ExplorerScreen({super.key, required this.query});

  final ExplorerQuery query;

  @override
  State<ExplorerScreen> createState() => _ExplorerScreenState();
}

class _ExplorerScreenState extends State<ExplorerScreen> {
  late final ExplorerViewModel _vm = ExplorerViewModel(
    players: context.read<PlayerRepository>(),
    navigate: _go,
  );
  late final DossierViewModel _dossier = DossierViewModel(
    players: context.read<PlayerRepository>(),
  );
  late final DossierExit _exit = DossierExit(
    dossier: _dossier,
    playerId: () => widget.query.playerId,
    mounted: () => mounted,
    rebuild: () => setState(() {}),
  );
  // True only the first time the app shows this view: the table's first
  // rows then enter staggered (DESIGN.md §5).
  late final bool _firstLoad =
      context.read<FirstLoadTracker?>()?.claim('explorer') ?? false;
  final ExplorerFocus _focus = ExplorerFocus();

  @override
  void initState() {
    super.initState();
    _vm.applyQuery(widget.query);
    _dossier.show(widget.query.playerId);
    _vm.addListener(_onExplorerChange);
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void didUpdateWidget(ExplorerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final closed = oldWidget.query.playerId;
    final opened = widget.query.playerId;
    if (closed != null && opened == null) {
      _focus.returnAfterClose(closed, mounted: () => mounted);
    }
    if (closed != opened) {
      final row = _vm.page?.players.where((p) => p.id == opened).firstOrNull;
      announceDossier(
        context,
        dossierAnnouncement(opened: opened, name: row?.name),
      );
    }
    // Decided before the query is applied, while the status is still the
    // one the slot was built for.
    final exitPlays = DossierExit.plays(context, _vm.status);
    _vm.applyQuery(widget.query);
    _exit.queryChanged(closed: closed, opened: opened, exitPlays: exitPlays);
  }

  @override
  void dispose() {
    _vm.removeListener(_onExplorerChange);
    HardwareKeyboard.instance.removeHandler(_onKey);
    _vm.dispose();
    _dossier.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _go(ExplorerQuery query) => context.go(query.toLocation());

  void _onExplorerChange() => _exit.explorerChanged(_vm.status);

  /// Escape closes the dossier from anywhere in view 1 (DESIGN.md §4),
  /// except while a select's list is open (its route is on top) or the
  /// search field has text (Escape clears it first).
  bool _onKey(KeyEvent event) {
    if (event is! KeyDownEvent ||
        event.logicalKey != LogicalKeyboardKey.escape ||
        !widget.query.isDossierOpen ||
        !(ModalRoute.of(context)?.isCurrent ?? false) ||
        (_focus.search.hasFocus && _vm.searchText.isNotEmpty)) {
      return false;
    }
    _vm.closeDossier();
    return true;
  }

  @override
  Widget build(BuildContext context) {
    final dataset = context.watch<DatasetViewModel?>();
    return ListenableBuilder(
      listenable: _vm,
      builder: (context, _) => ExplorerLayout(
        vm: _vm,
        dossier: _dossier,
        presentation: DossierPresentation.forWidth(
          MediaQuery.sizeOf(context).width,
        ),
        datasetTotal: dataset?.totalPlayers,
        staggerFirstLoad: _firstLoad,
        dossierExiting: _exit.exiting,
        onDossierExited: _exit.finish,
        rowFocus: _focus.rows,
        tableFocus: _focus.table,
        searchFocus: _focus.search,
        dossierFocus: _focus.dossier,
        onRetry: () {
          _vm.retry();
          if (dataset?.overview == null) dataset?.load();
        },
      ),
    );
  }
}
