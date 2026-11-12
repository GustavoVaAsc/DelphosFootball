/// A dossier part that could not be loaded (the header or a section): one
/// sentence and "Reintentar", in place of the content.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/action_button.dart';

/// The error line of a dossier part.
class DossierLoadError extends StatelessWidget {
  const DossierLoadError({
    super.key,
    required this.onRetry,
    this.message = 'No se pudo cargar la ficha de este jugador.',
  });

  final VoidCallback onRetry;
  final String message;

  @override
  Widget build(BuildContext context) => Row(
    spacing: 12,
    children: [
      Flexible(
        child: Text(message, style: DelphosText.ui(color: DelphosColors.ink2)),
      ),
      ActionButton(label: 'Reintentar', primary: true, onPressed: onRetry),
    ],
  );
}
