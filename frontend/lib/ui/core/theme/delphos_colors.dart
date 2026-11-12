/// The colour tokens of DESIGN.md §2, one constant per token, exact hexes.
/// Each colour has one job; the role comments repeat DESIGN.md's.
library;

import 'package:flutter/widgets.dart';

/// Colour tokens of the light front-office theme.
abstract final class DelphosColors {
  /// App background (warm newsprint paper).
  static const Color canvas = Color(0xFFF4F2EC);

  /// Table, dossier, panels.
  static const Color surface = Color(0xFFFFFFFF);

  /// Table header, row hover, pitch glyph ground.
  static const Color surfaceSubtle = Color(0xFFFAF9F6);

  /// "En precio" pill ground, neutral fills.
  static const Color surfaceMuted = Color(0xFFEEEBE3);

  /// Primary text, figures, sidebar, focus ring, selected row bar.
  static const Color ink = Color(0xFF13233A);

  /// Secondary text.
  static const Color ink2 = Color(0xFF4A5568);

  /// Muted text, labels, placeholders.
  static const Color ink3 = Color(0xFF5E6673);

  /// Hairlines and dividers (decorative, not a control boundary).
  static const Color rule = Color(0xFFE3DFD6);

  /// Input, select and segmented-control borders.
  static const Color controlBorder = Color(0xFF7F8690);

  /// Pitch markings in glyphs and banners.
  static const Color pitchLine = Color(0xFF8F8B81);

  /// The zone of a pitch glyph: ink at 16%, as the preview's
  /// `--pitch-zone-fill`.
  static const Color pitchZoneFill = Color(0x2913233A);

  /// Selected table row (ink tint).
  static const Color selectedBg = Color(0xFFEDEFF2);

  /// Only "undervalued", and better-than-reference comparator deltas.
  static const Color up = Color(0xFF0B6E4F);

  /// Ground of the "Infravalorado" pill.
  static const Color upBg = Color(0xFFE6F1EC);

  /// Only "overvalued", and worse-than-reference comparator deltas.
  static const Color down = Color(0xFFB3261E);

  /// Ground of the "Sobrevalorado" pill.
  static const Color downBg = Color(0xFFF8E8E6);

  /// Navy sidebar (same hue as ink).
  static const Color sidebarBg = Color(0xFF13233A);

  /// Active nav item ground.
  static const Color sidebarActive = Color(0xFF22395A);

  /// Nav labels.
  static const Color sidebarText = Color(0xFFC9D1DC);

  /// Sidebar subtitle and footer.
  static const Color sidebarMuted = Color(0xFF9AA7B8);

  /// Sidebar hairlines (white at 10%, as in the design preview).
  static const Color sidebarRule = Color(0x1AFFFFFF);

  /// Nav item hover ground (white at 6%, as in the design preview).
  static const Color sidebarHover = Color(0x0FFFFFFF);

  /// Shadow of the one floating element, the crest disc (ink at 12%).
  static const Color floatShadow = Color(0x1F13233A);

  /// Border of the brand tile (white at 28%, as in the design preview).
  static const Color sidebarMarkBorder = Color(0x47FFFFFF);

  /// White text and the focus ring on the navy sidebar.
  static const Color onSidebar = Color(0xFFFFFFFF);
}
