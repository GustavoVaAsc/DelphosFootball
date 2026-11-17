/// The card of the capabilities pop-up: title and close button, the intro,
/// each capability, the quick examples and "Entendido".
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_shadows.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import 'chat_capabilities_content.dart';
import 'chat_capability_row.dart';
import 'chat_close_button.dart';

/// The 580 px card.
class ChatCapabilitiesCard extends StatelessWidget {
  const ChatCapabilitiesCard({
    super.key,
    required this.onClose,
    required this.onPickPrompt,
    required this.closeFocus,
  });

  final VoidCallback onClose;
  final ValueChanged<String> onPickPrompt;

  /// The close button's focus node: the pop-up focuses it when it opens.
  final FocusNode closeFocus;

  @override
  Widget build(BuildContext context) => Container(
    width: 580,
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      color: DelphosColors.surface,
      borderRadius: BorderRadius.circular(DelphosRadius.card),
      border: Border.all(color: DelphosColors.rule),
      boxShadow: DelphosShadows.float,
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 14,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '¿Qué puede hacer PitIA?',
                style: DelphosText.ui(
                  size: TypeScale.title,
                  weight: FontWeight.w700,
                ),
              ),
            ),
            ChatCloseButton(onPressed: onClose, focusNode: closeFocus),
          ],
        ),
        Text(
          'Escribe una petición o pide comparar jugadores. PitIA responde con los datos del modelo y muestra cada consulta que hace.',
          style: DelphosText.ui(color: DelphosColors.ink2, height: 1.45),
        ),
        for (final (title, desc) in chatCapabilities)
          ChatCapabilityRow(title: title, description: desc),
        Container(
          padding: const EdgeInsets.only(top: 8),
          decoration: const BoxDecoration(
            border: Border(top: BorderSide(color: DelphosColors.rule)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 8,
            children: [
              Text(
                'Ejemplos rápidos',
                style: DelphosText.ui(
                  size: TypeScale.secondary,
                  weight: FontWeight.w600,
                  color: DelphosColors.ink3,
                ),
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final (label, prompt) in chatSamplePrompts)
                    ActionButton(
                      label: label,
                      onPressed: () => onPickPrompt(prompt),
                    ),
                ],
              ),
            ],
          ),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: ActionButton(
            label: 'Entendido',
            primary: true,
            onPressed: onClose,
          ),
        ),
      ],
    ),
  );
}
