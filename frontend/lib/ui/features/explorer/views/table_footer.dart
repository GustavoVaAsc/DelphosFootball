/// The market table's footer: the count line and, when the list spans
/// pages, "Anterior" and "Siguiente" (disabled at the ends).
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';

/// A 40 px bar under the rows.
class TableFooter extends StatelessWidget {
  const TableFooter({
    super.key,
    required this.text,
    this.page = 1,
    this.totalPages = 1,
    this.onPage,
  });

  final String text;
  final int page;
  final int totalPages;

  /// Moves to a page; `null` hides the page controls.
  final ValueChanged<int>? onPage;

  @override
  Widget build(BuildContext context) {
    final pager = onPage;
    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: const BoxDecoration(
        color: DelphosColors.surfaceSubtle,
        border: Border(top: BorderSide(color: DelphosColors.rule)),
      ),
      child: Row(
        spacing: 8,
        children: [
          Expanded(
            child: Semantics(
              liveRegion: true,
              child: Text(
                text,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: DelphosText.ui(
                  size: TypeScale.secondary,
                  color: DelphosColors.ink2,
                  tabular: true,
                ),
              ),
            ),
          ),
          if (pager != null && totalPages > 1) ...[
            ActionButton(
              label: 'Anterior',
              onPressed: page > 1 ? () => pager(page - 1) : null,
            ),
            ActionButton(
              label: 'Siguiente',
              onPressed: page < totalPages ? () => pager(page + 1) : null,
            ),
          ],
        ],
      ),
    );
  }
}
