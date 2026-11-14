/// Top header of the conversational scouting assistant module.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';

/// Displays module title, subtitle, and actions to inspect capabilities or reset.
class ChatHeader extends StatelessWidget {
  const ChatHeader({
    super.key,
    required this.hasTurns,
    required this.onOpenCapabilities,
    required this.onClear,
  });

  final bool hasTurns;
  final VoidCallback onOpenCapabilities;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: const BoxDecoration(
        color: DelphosColors.surface,
        border: Border(bottom: BorderSide(color: DelphosColors.rule)),
      ),
      child: Row(
        spacing: 12,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              spacing: 2,
              children: [
                Text(
                  'Asistente de Scouting',
                  style: DelphosText.condensed(size: TypeScale.title),
                ),
                Text(
                  'Consultas en lenguaje natural y comparaciones con datos calculados por el modelo',
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    color: DelphosColors.ink2,
                  ),
                ),
              ],
            ),
          ),
          ActionButton(
            label: '¿Qué puede hacer el agente?',
            onPressed: onOpenCapabilities,
          ),
          if (hasTurns)
            ActionButton(label: 'Nueva conversación', onPressed: onClear),
        ],
      ),
    );
  }
}
