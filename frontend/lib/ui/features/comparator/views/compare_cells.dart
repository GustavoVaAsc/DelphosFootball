/// The cell faces of the comparison table (DESIGN.md §4 and §2): euro
/// figures in the condensed cut, plain values with a signed delta beside
/// them (toned only when the rules say so), muted notes, and a static
/// placeholder while a candidate's season loads.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'compare_rules.dart';
import 'delta_tone.dart';

/// Builders for one cell's content.
abstract final class CompareCells {
  /// A euro figure, 15/700 condensed, in [colour].
  static Widget figure(String text, {Color colour = DelphosColors.ink}) =>
      Text(text, style: DelphosText.condensed(color: colour));

  /// A value, with its delta when there is one.
  static Widget value(CompareCell cell) => Wrap(
    spacing: 8,
    crossAxisAlignment: WrapCrossAlignment.end,
    children: [
      Text(
        cell.text,
        style: DelphosText.ui(weight: FontWeight.w500, tabular: true),
      ),
      if (cell.delta case final delta?)
        Text(
          delta,
          softWrap: false,
          style: DelphosText.ui(
            size: TypeScale.secondary,
            tabular: true,
            color: switch (cell.tone) {
              DeltaTone.up => DelphosColors.up,
              DeltaTone.down => DelphosColors.down,
              DeltaTone.neutral => DelphosColors.ink3,
            },
          ),
        ),
    ],
  );

  /// A plain value with no delta.
  static Widget plain(String text) =>
      value((text: text, delta: null, tone: DeltaTone.neutral));

  /// A muted note ("No aplica", "Sin datos de temporada").
  static Widget note(String text) => Text(
    text,
    style: DelphosText.ui(size: TypeScale.secondary, color: DelphosColors.ink3),
  );

  /// A static bar while a value loads (no shimmer).
  static Widget pending() => ExcludeSemantics(
    child: Container(
      width: 60,
      height: 10,
      decoration: BoxDecoration(
        color: DelphosColors.surfaceMuted,
        borderRadius: BorderRadius.circular(4),
      ),
    ),
  );
}
