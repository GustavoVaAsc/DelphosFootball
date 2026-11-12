/// The centred message panel of DESIGN.md §7: a title, one plain sentence,
/// and at most one action. Used for the error and empty states.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';

/// A state message, announced to screen readers as a live region.
class StatePanel extends StatelessWidget {
  const StatePanel({
    super.key,
    required this.title,
    required this.text,
    this.action,
  });

  final String title;
  final String text;

  /// The one way forward ("Reintentar", "Restablecer filtros").
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      container: true,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              spacing: 10,
              children: [
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: DelphosText.ui(
                    size: TypeScale.section,
                    weight: FontWeight.w700,
                  ),
                ),
                Text(
                  text,
                  textAlign: TextAlign.center,
                  style: DelphosText.ui(color: DelphosColors.ink2),
                ),
                if (action case final action?)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: action,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
