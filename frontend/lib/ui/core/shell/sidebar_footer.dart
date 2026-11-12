/// The sidebar's one-line footer (DESIGN.md §4, Sidebar): "5.522 jugadores
/// · 2025/26", derived from the data, and nothing until the data answers.
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../format/dates.dart';
import '../format/numbers.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';
import '../view_models/dataset_view_model.dart';

/// The player total and the season.
class SidebarFooter extends StatelessWidget {
  const SidebarFooter({super.key});

  @override
  Widget build(BuildContext context) {
    final dataset = context.watch<DatasetViewModel?>();
    final overview = dataset?.overview;
    if (overview == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: DelphosColors.sidebarRule)),
      ),
      child: Text(
        '${formatCount(overview.totalPlayers, 'jugador', 'jugadores')}'
        ' · ${formatSeason(overview.season)}',
        maxLines: 1,
        softWrap: false,
        style: DelphosText.ui(
          size: TypeScale.secondary,
          color: DelphosColors.sidebarMuted,
          tabular: true,
        ),
      ),
    );
  }
}
