/// How the player dossier opens at a given window width (ADR-027).
///
/// The app is designed for 1280 to 1920 px. From [sidePanelMinWidth] up the
/// dossier is a 440 px side panel beside the table; below it, the dossier
/// opens as its own full-width page. There is no phone layout.
library;

/// The two ways the dossier can open.
enum DossierPresentation {
  /// A fixed 440 px panel beside the market table.
  sidePanel,

  /// A full-width page in place of the table.
  fullPage;

  /// The narrowest window that still fits the table beside the panel.
  static const double sidePanelMinWidth = 1100;

  /// The presentation for a window [width] in logical pixels.
  static DossierPresentation forWidth(double width) =>
      width >= sidePanelMinWidth ? sidePanel : fullPage;
}
