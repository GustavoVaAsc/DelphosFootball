/// Progress trail showing what the scouting assistant consulted. It has no
/// border or ground: the assistant bubble around it is the only bordered
/// container.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_tool_step.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/shimmer_text.dart';
import 'chat_step_row.dart';

/// Renders tool-call execution steps in plain Spanish, never raw function
/// names. While the turn streams, the label that is currently working
/// shimmers: the first wait, a running step, or the wait after a result.
class ChatStepTrail extends StatelessWidget {
  const ChatStepTrail({
    super.key,
    required this.steps,
    required this.isStreaming,
  });

  final List<ChatToolStep> steps;
  final bool isStreaming;

  @override
  Widget build(BuildContext context) {
    if (steps.isEmpty && !isStreaming) return const SizedBox.shrink();
    final heading = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w600,
      color: DelphosColors.ink2,
    );
    final waiting = isStreaming && !steps.any((step) => step.isRunning);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 6,
      children: [
        if (isStreaming && steps.isEmpty)
          ShimmerText('Analizando tu petición…', style: heading)
        else
          Text('Pasos realizados sobre la base del modelo', style: heading),
        for (final step in steps) ChatStepRow(step: step),
        if (waiting && steps.isNotEmpty)
          ShimmerText(
            'Analizando los resultados…',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              color: DelphosColors.ink3,
            ),
          ),
      ],
    );
  }
}
