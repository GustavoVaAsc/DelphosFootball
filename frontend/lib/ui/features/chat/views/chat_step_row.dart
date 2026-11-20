/// One step of the assistant's trail: a marker (a dot while it runs, a check
/// once it is done, a cross when it failed), its sentence and, once it ends,
/// the outcome.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_tool_step.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/line_glyph.dart';
import '../../../core/widgets/shimmer_text.dart';

/// A running step shimmers its sentence; a finished one is static text.
class ChatStepRow extends StatelessWidget {
  const ChatStepRow({super.key, required this.step});

  final ChatToolStep step;

  @override
  Widget build(BuildContext context) {
    final running = step.isRunning;
    final sentenceStyle = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w600,
      color: running ? DelphosColors.ink2 : DelphosColors.ink,
    );
    final outcome = step.isError ? 'No se pudo completar' : step.summary;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: SizedBox(
            width: 12,
            height: 12,
            child: switch (step.state) {
              ChatStepState.running => const Center(child: _RunningDot()),
              ChatStepState.done => const LineGlyph.check(),
              ChatStepState.failed => const LineGlyph.close(
                size: 10,
                color: DelphosColors.ink3,
              ),
            },
          ),
        ),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 2,
            children: [
              running
                  ? ShimmerText(step.stepTitle, style: sentenceStyle)
                  : Text(step.stepTitle, style: sentenceStyle),
              if (outcome.isNotEmpty)
                Text(
                  outcome,
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    color: DelphosColors.ink2,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// The marker of a step that has not answered yet.
class _RunningDot extends StatelessWidget {
  const _RunningDot();

  @override
  Widget build(BuildContext context) => const DecoratedBox(
    decoration: BoxDecoration(
      color: DelphosColors.ink3,
      shape: BoxShape.circle,
    ),
    child: SizedBox(width: 6, height: 6),
  );
}
