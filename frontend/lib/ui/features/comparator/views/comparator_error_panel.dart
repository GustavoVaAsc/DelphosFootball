/// The comparator's error state (DESIGN.md §7): the same panel as the
/// explorer's, "No se pudo conectar con el servidor de datos", one plain
/// sentence and "Reintentar".
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';

/// The panel shown when the reference player cannot be loaded.
class ComparatorErrorPanel extends StatelessWidget {
  const ComparatorErrorPanel({super.key, required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
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
