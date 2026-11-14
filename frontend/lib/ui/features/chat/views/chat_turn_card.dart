/// Renders one question-and-answer turn in the scouting assistant feed.
library;

import 'package:material_ui/material_ui.dart';

import '../../../../domain/models/chat_turn.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'chat_step_trail.dart';

/// Displays the user prompt, natural-language tool steps, and assistant answer.
class ChatTurnCard extends StatelessWidget {
  const ChatTurnCard({super.key, required this.turn});

  final ChatTurn turn;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 12,
        children: [
          Text(
            'Dirección deportiva',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w600,
              color: DelphosColors.ink3,
            ),
          ),
          Text(
            turn.userMessage,
            style: DelphosText.ui(
              size: TypeScale.section,
              weight: FontWeight.w600,
            ),
          ),
          if (turn.steps.isNotEmpty || turn.isStreaming)
            ChatStepTrail(steps: turn.steps, isStreaming: turn.isStreaming),
          if (turn.assistantMessage case final answer?)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: SelectableText(
                answer,
                style: DelphosText.prose(color: DelphosColors.ink),
              ),
            ),
          if (turn.errorMessage case final error?)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: DelphosColors.surfaceSubtle,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: DelphosColors.rule),
              ),
              child: Text(
                error,
                style: DelphosText.ui(color: DelphosColors.ink2, height: 1.45),
              ),
            ),
        ],
      ),
    );
  }
}
