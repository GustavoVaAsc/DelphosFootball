/// The state of the dossier panel's exit animation (DESIGN.md §5) for the
/// explorer screen: a close that plays the exit keeps the closing player's
/// content in `DossierViewModel` until the slot reports the exit has ended,
/// so the panel never shows skeletons while it leaves, and the table keeps
/// the open layout meanwhile.
library;

import 'package:flutter/widgets.dart';

import '../../../core/layout/dossier_presentation.dart';
import '../../../core/theme/motion.dart';
import '../view_models/dossier_view_model.dart';
import '../view_models/explorer_status.dart';

/// Decides when the dossier view model is cleared.
class DossierExit {
  DossierExit({
    required this.dossier,
    required this.playerId,
    required this.mounted,
    required this.rebuild,
  });

  final DossierViewModel dossier;

  /// The player in the URL now.
  final int? Function() playerId;
  final bool Function() mounted;

  /// Asks the screen to rebuild (the table's layout depends on [exiting]).
  final VoidCallback rebuild;

  bool _exiting = false;

  /// True from the start of an animated close until its exit ends.
  bool get exiting => _exiting;

  /// Whether closing the dossier now plays the side panel's exit: the slot
  /// exists only in the side-panel layout and outside the error state, and
  /// reduced motion has no exit.
  static bool plays(BuildContext context, ExplorerStatus status) =>
      status != ExplorerStatus.error &&
      DossierPresentation.forWidth(MediaQuery.sizeOf(context).width) ==
          DossierPresentation.sidePanel &&
      DelphosMotion.duration(context, DelphosMotion.panel) > Duration.zero;

  /// The URL's player changed from [closed] to [opened] (either may be
  /// `null`); [exitPlays] was decided before the query was applied.
  void queryChanged({
    required int? closed,
    required int? opened,
    required bool exitPlays,
  }) {
    if (opened != null) {
      _exiting = false;
      dossier.show(opened);
    } else if (closed != null && exitPlays) {
      _exiting = true;
    } else if (!_exiting) {
      dossier.show(null);
    }
    // Otherwise a filter or search changed during the exit: keep the content
    // until the exit ends.
  }

  /// Ends an exit (or any close): shows the player in the URL, or clears the
  /// dossier for none. Only an exit asks for a rebuild: anything else may
  /// run during a build, where that is not allowed.
  void finish() {
    final wasExiting = _exiting;
    _exiting = false;
    dossier.show(playerId());
    if (wasExiting && mounted()) rebuild();
  }

  /// An error state unmounts the slot, so its exit would never report back.
  void explorerChanged(ExplorerStatus status) {
    if (_exiting && status == ExplorerStatus.error) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted() && _exiting) finish();
      });
    }
  }
}
