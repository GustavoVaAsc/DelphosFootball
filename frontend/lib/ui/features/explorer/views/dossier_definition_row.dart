/// Line 3 of the dossier header (DESIGN.md §4): the definition row Edad ·
/// Altura · Pie · Posición with hairline separators. It wraps between items,
/// never inside one, and the item that starts a line shows no hairline: every
/// item carries its leading hairline and 10 px, the row is drawn 11 px to the
/// left and that strip is clipped, as in the preview. Items the data lacks
/// are left out by the caller.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// A row of (term, value) pairs.
class DossierDefinitionRow extends StatelessWidget {
  const DossierDefinitionRow({super.key, required this.items});

  final List<(String, String)> items;

  @override
  Widget build(BuildContext context) {
    final term = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink3,
      tabular: true,
    );
    final value = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w500,
      tabular: true,
    );
    return ClipRect(
      child: Transform.translate(
        offset: const Offset(-11, 0),
        child: Wrap(
          runSpacing: 4,
          children: [
            for (final (label, text) in items)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                decoration: const BoxDecoration(
                  border: Border(left: BorderSide(color: DelphosColors.rule)),
                ),
                child: Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: '$label ', style: term),
                      TextSpan(text: text, style: value),
                    ],
                  ),
                  maxLines: 1,
                  softWrap: false,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
