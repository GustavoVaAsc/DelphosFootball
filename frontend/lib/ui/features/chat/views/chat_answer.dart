/// The assistant's answer as prose, capped at the 68-character measure.
library;

import 'package:material_ui/material_ui.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';

/// Serif prose in ink-2; `**text**` is emphasised in ink.
class ChatAnswer extends StatelessWidget {
  const ChatAnswer({super.key, required this.text});

  final String text;

  /// The maximum measure, in characters (DESIGN.md §3).
  static const int measure = 68;

  @override
  Widget build(BuildContext context) {
    final style = DelphosText.prose(color: DelphosColors.ink2);
    final zero = TextPainter(
      text: TextSpan(text: '0', style: style),
      textDirection: TextDirection.ltr,
      textScaler: MediaQuery.textScalerOf(context),
    )..layout();
    final maxWidth = zero.width * measure;
    zero.dispose();
    final emphasis = DelphosText.prose(
      weight: FontWeight.w600,
      color: DelphosColors.ink,
    );
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: SelectableText.rich(
        TextSpan(
          style: style,
          children: [
            for (final (i, part) in text.split('**').indexed)
              TextSpan(text: part, style: i.isOdd ? emphasis : null),
          ],
        ),
      ),
    );
  }
}
