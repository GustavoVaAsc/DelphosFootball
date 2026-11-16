/// Renders one question-and-answer turn in the scouting assistant feed.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_turn.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'chat_answer.dart';
import 'chat_hairline.dart';
import 'chat_step_trail.dart';
import 'chat_turn_error.dart';

/// Displays the user prompt, tool steps and answer. It is the only card of
/// the turn: the trail and the error sit inside it, set off by hairlines.
class ChatTurnCard extends StatelessWidget {
  const ChatTurnCard({super.key, required this.turn, this.onRetry});

  final ChatTurn turn;

  /// Resends the turn; offered only while the turn shows an error.
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(DelphosRadius.card),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 12,
        children: [
          Text(
            'Dirección Deportiva',
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
          if (turn.steps.isNotEmpty || turn.isStreaming) ...[
            const ChatHairline(),
            ChatStepTrail(steps: turn.steps, isStreaming: turn.isStreaming),
          ],
          if (turn.assistantMessage case final answer?) ...[
            const ChatHairline(),
            Align(
              alignment: Alignment.centerLeft,
              child: ChatAnswer(text: answer),
            ),
          ],
          if (turn.errorMessage case final error?) ...[
            const ChatHairline(),
            ChatTurnError(message: error, onRetry: onRetry),
          ],
        ],
      ),
    );
  }
}
