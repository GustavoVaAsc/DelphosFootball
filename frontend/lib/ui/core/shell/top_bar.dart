/// The top bar (DESIGN.md §4, Top bar): the page title and one line of
/// plain metadata from the data, "Temporada 2025/26 · datos al 5 jun 2026",
/// or only the season until the backend sends the data date.
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../format/dates.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';
import '../view_models/dataset_view_model.dart';

/// A 56 px bar on surface with a hairline below.
class TopBar extends StatelessWidget {
  const TopBar({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final overview = context.watch<DatasetViewModel?>()?.overview;
    final meta = overview == null
        ? null
        : [
            'Temporada ${formatSeason(overview.season)}',
            if (overview.asOfDate case final date?)
              'datos al ${formatDate(date)}',
          ].join(' · ');
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: const BoxDecoration(
        color: DelphosColors.surface,
        border: Border(bottom: BorderSide(color: DelphosColors.rule)),
      ),
      child: Row(
        spacing: 16,
        children: [
          Expanded(
            child: Semantics(
              header: true,
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: DelphosText.ui(
                  size: TypeScale.title,
                  weight: FontWeight.w700,
                ),
              ),
            ),
          ),
          if (meta != null)
            Text(
              meta,
              maxLines: 1,
              softWrap: false,
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink3,
                tabular: true,
              ),
            ),
        ],
      ),
    );
  }
}
