/// Text style builders for the app's typography voices: League Spartan for
/// prominent headings and titles (>= 15 px), Source Sans 3 for compact UI
/// labels and controls (< 15 px), Archivo condensed with tabular figures for
/// player names and euro figures, and Source Serif 4 for report prose.
///
/// All bundled families are variable fonts. A variable font is shaped by its
/// axes, so every style sets the `wght` axis from its weight (and `wdth` or
/// `opsz` where they apply) alongside `fontWeight`.
library;

import 'package:flutter/widgets.dart';

import 'delphos_colors.dart';
import 'type_scale.dart';

/// Builds the app's text styles.
abstract final class DelphosText {
  static const String displayFamily = 'LeagueSpartan';
  static const String sansFamily = 'SourceSans3';
  static const String condensedFamily = 'Archivo';
  static const String serifFamily = 'SourceSerif4';

  /// Archivo's `wdth` value for the condensed cut (CSS `font-stretch: 80%`).
  static const double condensedWidth = 80;

  static const List<FontFeature> _tabular = [FontFeature.tabularFigures()];

  /// League Spartan for prominent headings (`size >= 15`) and Source Sans 3
  /// for smaller labels, controls, table body and navigation.
  static TextStyle ui({
    double size = TypeScale.body,
    FontWeight weight = FontWeight.w400,
    Color color = DelphosColors.ink,
    double? height,
    bool tabular = false,
  }) => TextStyle(
    fontFamily: size >= TypeScale.section ? displayFamily : sansFamily,
    fontSize: size,
    fontWeight: weight,
    fontVariations: [FontVariation('wght', weight.value.toDouble())],
    fontFeatures: tabular ? _tabular : null,
    color: color,
    height: height,
  );

  /// Archivo condensed with tabular figures: player names and euro figures.
  static TextStyle condensed({
    double size = TypeScale.section,
    FontWeight weight = FontWeight.w700,
    Color color = DelphosColors.ink,
    double? height,
  }) => TextStyle(
    fontFamily: condensedFamily,
    fontSize: size,
    fontWeight: weight,
    fontVariations: [
      FontVariation('wght', weight.value.toDouble()),
      const FontVariation('wdth', condensedWidth),
    ],
    fontFeatures: _tabular,
    color: color,
    height: height,
  );

  /// Source Serif 4 for scouting and report prose: 15px, line-height 1.55,
  /// with the optical size matched to the font size.
  static TextStyle prose({
    FontWeight weight = FontWeight.w400,
    FontStyle style = FontStyle.normal,
    Color color = DelphosColors.ink,
  }) => TextStyle(
    fontFamily: serifFamily,
    fontSize: TypeScale.section,
    fontWeight: weight,
    fontStyle: style,
    fontVariations: [
      FontVariation('wght', weight.value.toDouble()),
      const FontVariation('opsz', TypeScale.section),
    ],
    color: color,
    height: 1.55,
  );
}
