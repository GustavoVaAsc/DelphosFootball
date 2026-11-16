/// The one panel across the explorer when the data is unreachable (DESIGN.md
/// §7): a sentence and "Reintentar". The dossier stays closed meanwhile.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';

/// The unreachable-server panel.
class ExplorerErrorPanel extends StatelessWidget {
  const ExplorerErrorPanel({super.key, required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(DelphosRadius.card),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: StatePanel(
        title: 'No se pudo conectar con el servidor de datos',
        text:
            'Los datos del mercado no están disponibles ahora mismo. '
            'Comprueba la conexión e inténtalo de nuevo.',
        action: ActionButton(
          label: 'Reintentar',
          primary: true,
          onPressed: onRetry,
        ),
      ),
    );
  }
}
