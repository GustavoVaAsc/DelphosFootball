/// The app's Material theme, built from the DESIGN.md tokens. Light only.
///
/// Material supplies the plumbing (text selection, scrollbars, tooltips);
/// the look comes from the tokens. Ink ripples are off because the design's
/// motion is a calm 160 ms colour change, not a splash (DESIGN.md §5).
library;

import 'package:material_ui/material_ui.dart';

import 'delphos_colors.dart';
import 'delphos_text.dart';
import 'type_scale.dart';

/// Builds the light theme from the DESIGN.md tokens.
ThemeData buildDelphosTheme() {
  const scheme = ColorScheme.light(
    primary: DelphosColors.ink,
    onPrimary: DelphosColors.surface,
    secondary: DelphosColors.ink2,
    onSecondary: DelphosColors.surface,
    surface: DelphosColors.surface,
    onSurface: DelphosColors.ink,
    onSurfaceVariant: DelphosColors.ink3,
    surfaceContainerLowest: DelphosColors.surface,
    surfaceContainerLow: DelphosColors.surfaceSubtle,
    surfaceContainer: DelphosColors.surfaceSubtle,
    surfaceContainerHigh: DelphosColors.surfaceMuted,
    surfaceContainerHighest: DelphosColors.surfaceMuted,
    outline: DelphosColors.controlBorder,
    outlineVariant: DelphosColors.rule,
    error: DelphosColors.down,
    onError: DelphosColors.surface,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: DelphosColors.canvas,
    canvasColor: DelphosColors.canvas,
    dividerColor: DelphosColors.rule,
    fontFamily: DelphosText.sansFamily,
    splashFactory: NoSplash.splashFactory,
    focusColor: DelphosColors.selectedBg,
    hoverColor: DelphosColors.surfaceSubtle,
    textTheme: TextTheme(
      titleLarge: DelphosText.ui(
        size: TypeScale.title,
        weight: FontWeight.w700,
      ),
      titleMedium: DelphosText.ui(
        size: TypeScale.section,
        weight: FontWeight.w700,
      ),
      bodyLarge: DelphosText.ui(size: TypeScale.section),
      bodyMedium: DelphosText.ui(height: 1.45),
      bodySmall: DelphosText.ui(
        size: TypeScale.secondary,
        color: DelphosColors.ink2,
      ),
      labelMedium: DelphosText.ui(
        size: TypeScale.secondary,
        weight: FontWeight.w500,
      ),
      labelSmall: DelphosText.ui(
        size: TypeScale.label,
        color: DelphosColors.ink3,
      ),
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: DelphosColors.ink,
      selectionColor: DelphosColors.selectedBg,
    ),
  );
}
