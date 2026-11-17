/// The chat's first screen: a card inviting the user to talk to the data,
/// with the way to open the capabilities guide.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import 'chat_opener_focus.dart';

/// Shown while the conversation has no turns.
class ChatEmptyState extends StatelessWidget {
  const ChatEmptyState({super.key, required this.onOpenCapabilities});

  final VoidCallback onOpenCapabilities;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(DelphosRadius.card),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 10,
        children: [
          Text(
            'Conversa con PitIA sobre los datos del modelo',
            style: DelphosText.ui(
              size: TypeScale.section,
              weight: FontWeight.w600,
            ),
          ),
          Text(
            'Pregunta por jugadores concretos, solicita comparaciones frente a sus reemplazos o filtra oportunidades infravaloradas. Verás en todo momento qué consultas realiza PitIA antes de responder.',
            style: DelphosText.ui(color: DelphosColors.ink2, height: 1.5),
          ),
          ChatOpenerFocus(
            builder: (context, focusOpener) => ActionButton(
              label: 'Ver guía de capacidades y ejemplos',
              onPressed: () {
                focusOpener();
                onOpenCapabilities();
              },
            ),
          ),
        ],
      ),
    );
  }
}
