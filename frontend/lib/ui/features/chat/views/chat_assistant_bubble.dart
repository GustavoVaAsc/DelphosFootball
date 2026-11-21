/// PitIA response bubble, aligned to the left with a circular monogram badge.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_turn.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'chat_answer.dart';
import 'chat_hairline.dart';
import 'chat_player_list.dart';
import 'chat_step_trail.dart';
import 'chat_turn_error.dart';

/// Displays PitIA's steps, answer, referenced player cards and retry error.
class ChatAssistantBubble extends StatelessWidget {
  const ChatAssistantBubble({super.key, required this.turn, this.onRetry});

  final ChatTurn turn;

  /// Resends the turn; offered only while the turn shows an error.
  final VoidCallback? onRetry;

  static const double _maxWidth = 760;
  static const BorderRadius _bubbleRadius = BorderRadius.only(
    topLeft: Radius.circular(DelphosRadius.small),
    topRight: Radius.circular(DelphosRadius.card),
    bottomLeft: Radius.circular(DelphosRadius.card),
    bottomRight: Radius.circular(DelphosRadius.card),
  );

  @override
  Widget build(BuildContext context) {
    final hasTrail = turn.steps.isNotEmpty || turn.isStreaming;
    final sections = <Widget>[
      if (hasTrail)
        ChatStepTrail(steps: turn.steps, isStreaming: turn.isStreaming),
      if (turn.assistantMessage case final answer?)
        Align(
          alignment: Alignment.centerLeft,
          widthFactor: 1.0,
          child: ChatAnswer(text: answer),
        ),
      if (turn.players.isNotEmpty) ChatPlayerList(players: turn.players),
      if (turn.errorMessage case final error?)
        ChatTurnError(message: error, onRetry: onRetry),
    ];
    if (sections.isEmpty) return const SizedBox.shrink();

    final children = <Widget>[
      for (final (i, section) in sections.indexed) ...[
        if (i > 0) const ChatHairline(),
        section,
      ],
    ];
    final stretch = hasTrail || sections.length > 1;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 10,
      children: [
        const _PitIaBadge(),
        Flexible(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: _maxWidth),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              spacing: 6,
              children: [
                Text(
                  'PitIA',
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    weight: FontWeight.w600,
                    color: DelphosColors.ink2,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  decoration: BoxDecoration(
                    color: DelphosColors.surface,
                    borderRadius: _bubbleRadius,
                    border: Border.all(color: DelphosColors.rule),
                  ),
                  child: Column(
                    crossAxisAlignment: stretch
                        ? CrossAxisAlignment.stretch
                        : CrossAxisAlignment.start,
                    spacing: 12,
                    children: children,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Circular PitIA monogram excluded from semantics so screen readers announce
/// only the sender label beside it.
class _PitIaBadge extends StatelessWidget {
  const _PitIaBadge();

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        width: 30,
        height: 30,
        alignment: Alignment.center,
        decoration: const BoxDecoration(
          color: DelphosColors.ink,
          shape: BoxShape.circle,
        ),
        child: Text(
          'P',
          style: DelphosText.ui(
            size: TypeScale.section,
            weight: FontWeight.w700,
            color: DelphosColors.onSidebar,
            height: 1.0,
          ),
        ),
      ),
    );
  }
}
