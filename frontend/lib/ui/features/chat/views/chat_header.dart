/// Top header of the conversational scouting assistant module.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import 'chat_opener_focus.dart';

/// Displays the module subtitle and actions to inspect capabilities or reset.
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
                  'Consultas y comparaciones de scouting con datos calculados por el modelo',
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    color: DelphosColors.ink2,
                  ),
                ),
              ],
            ),
          ),
          ChatOpenerFocus(
            builder: (context, focusOpener) => ActionButton(
              label: 'Capacidades de PitIA',
              onPressed: () {
                focusOpener();
                onOpenCapabilities();
              },
            ),
          ),
          if (hasTurns)
            ActionButton(label: 'Nueva conversación', onPressed: onClear),
        ],
      ),
    );
  }
}
