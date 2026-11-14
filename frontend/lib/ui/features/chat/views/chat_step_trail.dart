/// Natural-language progress trail showing what the scouting agent consulted.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_tool_step.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// Renders tool-call execution steps in plain Spanish, never raw function names.
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
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: DelphosColors.surfaceSubtle,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 6,
        children: [
          Text(
            isStreaming && steps.isEmpty
                ? 'Analizando tu petición con los datos del modelo…'
                : 'Pasos realizados sobre la base del modelo',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w600,
              color: DelphosColors.ink2,
            ),
          ),
          for (var i = 0; i < steps.length; i++)
            _StepRow(index: i + 1, step: steps[i]),
          if (isStreaming && steps.isNotEmpty)
            Text(
              'Redactando respuesta con los resultados obtenidos…',
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink3,
              ),
            ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.index, required this.step});

  final int index;
  final ChatToolStep step;

  @override
  Widget build(BuildContext context) {
    final accent = step.isError ? DelphosColors.down : DelphosColors.up;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Container(
          margin: const EdgeInsets.only(top: 5),
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: accent, shape: BoxShape.circle),
        ),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '$index. ${step.stepTitle}: ',
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    weight: FontWeight.w600,
                    color: DelphosColors.ink,
                  ),
                ),
                TextSpan(
                  text: step.summary,
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    color: DelphosColors.ink2,
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
