/// The Explorador de Mercado (DESIGN.md §4): the filter bar over the market
/// table, and the player dossier beside it (from 1100 px) or in its place
/// (narrower windows, ADR-027). The URL drives everything (ADR-024).
library;

import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../data/repositories/report_repository.dart';
import '../../../../routing/explorer_query.dart';
import '../../../core/layout/dossier_presentation.dart';
import '../../../core/view_models/dataset_view_model.dart';
import '../view_models/dossier_view_model.dart';
import '../view_models/explorer_view_model.dart';
import 'dossier_announcement.dart';
import 'explorer_layout.dart';
import 'row_focus_registry.dart';

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
    reports: context.read<ReportRepository>(),
  );
  final RowFocusRegistry _rowFocus = RowFocusRegistry();
  final FocusNode _tableFocus = FocusNode(debugLabel: 'player table');
  final FocusNode _searchFocus = FocusNode(debugLabel: 'player search');
  final FocusNode _dossierFocus = FocusNode(
    debugLabel: 'dossier',
    canRequestFocus: false,
    skipTraversal: true,
  );

  @override
  void initState() {
    super.initState();
    _vm.applyQuery(widget.query);
    _dossier.show(widget.query.playerId);
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void didUpdateWidget(ExplorerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final closed = oldWidget.query.playerId;
    final opened = widget.query.playerId;
    if (closed != null && opened == null) _returnFocusAfterClose(closed);
    if (closed != opened) {
      final row = _vm.page?.players.where((p) => p.id == opened).firstOrNull;
      announceDossier(
        context,
        dossierAnnouncement(opened: opened, name: row?.name),
      );
    }
    _vm.applyQuery(widget.query);
    _dossier.show(widget.query.playerId);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    _vm.dispose();
    _dossier.dispose();
    _rowFocus.dispose();
    _tableFocus.dispose();
    _searchFocus.dispose();
    _dossierFocus.dispose();
    super.dispose();
  }

  void _go(ExplorerQuery query) => context.go(query.toLocation());

  /// Escape closes the dossier from anywhere in view 1 (DESIGN.md §4),
  /// except while a select's list is open (its route is on top) or the
  /// search field has text (Escape clears it first).
  bool _onKey(KeyEvent event) {
    if (event is! KeyDownEvent ||
        event.logicalKey != LogicalKeyboardKey.escape ||
        !widget.query.isDossierOpen ||
        !(ModalRoute.of(context)?.isCurrent ?? false) ||
        (_searchFocus.hasFocus && _vm.searchText.isNotEmpty)) {
      return false;
    }
    _vm.closeDossier();
    return true;
  }

  /// Focus goes back to the player's name if it was inside the dossier, on
  /// that name already, or nowhere in particular (no node, a scope, or the
  /// table area); anywhere else it stays (DESIGN.md §4).
  void _returnFocusAfterClose(int playerId) {
    final primary = FocusManager.instance.primaryFocus;
    final moveFocus =
        _dossierFocus.hasFocus ||
        primary == null ||
        primary is FocusScopeNode ||
        primary == _tableFocus ||
        primary == _rowFocus.existing(playerId);
    if (!moveFocus) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      (_rowFocus.existing(playerId) ?? _tableFocus).requestFocus();
    });
  }

  @override
  Widget build(BuildContext context) {
    final dataset = context.watch<DatasetViewModel?>();
    return ListenableBuilder(
      listenable: Listenable.merge([_vm, _dossier]),
      builder: (context, _) => ExplorerLayout(
        vm: _vm,
        dossier: _dossier,
        presentation: DossierPresentation.forWidth(
          MediaQuery.sizeOf(context).width,
        ),
        datasetTotal: dataset?.totalPlayers,
        rowFocus: _rowFocus,
        tableFocus: _tableFocus,
        searchFocus: _searchFocus,
        dossierFocus: _dossierFocus,
        onRetry: () {
          _vm.retry();
          if (dataset?.overview == null) dataset?.load();
        },
      ),
    );
  }
}
